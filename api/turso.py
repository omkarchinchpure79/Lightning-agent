"""
turso.py — minimal sqlite3-compatible client for Turso (libSQL) over HTTP.

Why this exists: on serverless hosting the engine data (cutoffs, predictions,
colleges) ships as a read-only bundled SQLite file, but the five writable
API tables (counselors, student_profiles, student_shortlists,
counselor_shortlists, college_descriptions) must survive across invocations.
Turso is SQLite-over-HTTP, so the SQL dialect is identical — this shim just
speaks the Hrana v2 pipeline protocol with urllib (zero extra dependencies)
and mimics the small slice of the sqlite3 API the routes actually use:

    conn.execute(sql, params) -> cursor
    cursor.fetchone() / .fetchall() / iteration
    cursor.lastrowid / .rowcount
    conn.executescript(sql)
    conn.commit() / .close()          (no-ops — each execute autocommits)
    rows behave like sqlite3.Row      (row["col"], dict(row), iteration)

UNIQUE-constraint violations are re-raised as sqlite3.IntegrityError so the
routes' existing race handling (e.g. duplicate signup) works unchanged.
"""
import json
import sqlite3
import urllib.error
import urllib.request


class Row(dict):
    """dict subclass so both row["col"] and dict(row) work, plus int indexing."""

    def __init__(self, columns, values):
        super().__init__(zip(columns, values))
        self._values = values

    def __getitem__(self, key):
        if isinstance(key, int):
            return self._values[key]
        return super().__getitem__(key)


class Cursor:
    def __init__(self, rows, lastrowid, rowcount):
        self._rows = rows
        self._i = 0
        self.lastrowid = lastrowid
        self.rowcount = rowcount

    def fetchone(self):
        if self._i < len(self._rows):
            row = self._rows[self._i]
            self._i += 1
            return row
        return None

    def fetchall(self):
        rows = self._rows[self._i:]
        self._i = len(self._rows)
        return rows

    def __iter__(self):
        while True:
            row = self.fetchone()
            if row is None:
                return
            yield row


def _encode_arg(v):
    if v is None:
        return {"type": "null"}
    if isinstance(v, bool):
        return {"type": "integer", "value": str(int(v))}
    if isinstance(v, int):
        return {"type": "integer", "value": str(v)}
    if isinstance(v, float):
        return {"type": "float", "value": v}
    if isinstance(v, (bytes, bytearray)):
        import base64
        return {"type": "blob", "base64": base64.b64encode(bytes(v)).decode()}
    return {"type": "text", "value": str(v)}


def _decode_value(cell):
    t = cell.get("type")
    if t == "null":
        return None
    if t == "integer":
        return int(cell["value"])
    if t == "float":
        return float(cell["value"])
    if t == "blob":
        import base64
        return base64.b64decode(cell["base64"])
    return cell["value"]


class Connection:
    def __init__(self, url: str, auth_token: str, timeout: float = 30.0):
        # Marketplace URLs come as libsql://<host>; Hrana-over-HTTP wants https.
        if url.startswith("libsql://"):
            url = "https://" + url[len("libsql://"):]
        self._endpoint = url.rstrip("/") + "/v2/pipeline"
        self._token = auth_token
        self._timeout = timeout

    def _pipeline(self, statements):
        requests_ = [{"type": "execute", "stmt": s} for s in statements]
        requests_.append({"type": "close"})
        body = json.dumps({"requests": requests_}).encode()
        req = urllib.request.Request(
            self._endpoint,
            data=body,
            headers={
                "Authorization": f"Bearer {self._token}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=self._timeout) as resp:
                payload = json.loads(resp.read())
        except urllib.error.HTTPError as e:
            raise sqlite3.OperationalError(
                f"Turso HTTP {e.code}: {e.read().decode(errors='replace')[:500]}"
            ) from e

        results = []
        for res in payload.get("results", []):
            if res.get("type") == "error":
                msg = res.get("error", {}).get("message", "unknown Turso error")
                if "UNIQUE constraint" in msg or "SQLITE_CONSTRAINT" in msg:
                    raise sqlite3.IntegrityError(msg)
                raise sqlite3.OperationalError(msg)
            results.append(res.get("response", {}).get("result"))
        return results

    def execute(self, sql: str, params=()):
        stmt = {"sql": sql, "args": [_encode_arg(p) for p in params]}
        result = self._pipeline([stmt])[0] or {}
        columns = [c.get("name") for c in result.get("cols", [])]
        rows = [Row(columns, [_decode_value(c) for c in r]) for r in result.get("rows", [])]
        lastrowid = result.get("last_insert_rowid")
        return Cursor(
            rows,
            int(lastrowid) if lastrowid is not None else None,
            result.get("affected_row_count", -1),
        )

    def executescript(self, script: str):
        stmts = [s.strip() for s in script.split(";") if s.strip()]
        self._pipeline([{"sql": s, "args": []} for s in stmts])

    def commit(self):
        pass  # every execute autocommits over Hrana HTTP

    def close(self):
        pass  # stateless HTTP — nothing to release


def connect(url: str, auth_token: str) -> Connection:
    return Connection(url, auth_token)
