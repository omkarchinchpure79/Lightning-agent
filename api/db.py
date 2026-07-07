"""
db.py — SQLite connection helper and table initialisation for the EduPath API.

Adds app/ to sys.path so engine_adapter is importable from routes.
Uses the same db/edupath.db as the existing engine — no separate API database.
Never touches existing tables; only creates the two new API-owned tables.
"""
import os
import sqlite3
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_APP_DIR = os.path.join(_ROOT, "app")
if _APP_DIR not in sys.path:
    sys.path.insert(0, _APP_DIR)

def _load_dotenv() -> None:
    """Load KEY=value from repo-root .env into os.environ (no extra dependencies)."""
    env_path = os.path.join(_ROOT, ".env")
    if not os.path.exists(env_path):
        return
    with open(env_path) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, val = line.partition("=")
            key = key.strip()
            val = val.strip().strip('"').strip("'")
            if key and key not in os.environ:
                os.environ[key] = val


_load_dotenv()

# EDUPATH_DB_PATH lets a deployment keep the DB on a persistent disk outside
# the repo (e.g. /data/edupath.db). Resolved after .env so either source works.
DB_PATH = os.environ.get("EDUPATH_DB_PATH") or os.path.join(_ROOT, "db", "edupath.db")


def get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def get_app_conn():
    """Connection for the five WRITABLE API-owned tables (counselors,
    student_profiles, student_shortlists, counselor_shortlists,
    college_descriptions).

    Locally this is the same SQLite file as get_conn(), so dev and tests are
    unchanged. On serverless hosting — where the engine DB is a read-only
    bundled snapshot — set TURSO_DATABASE_URL/TURSO_AUTH_TOKEN and writes go
    to Turso (SQLite-over-HTTP, same dialect) so they survive invocations.

    Engine tables (cutoffs, predictions_2026, colleges, …) do NOT exist on
    Turso — always read those through get_conn().
    """
    url = os.environ.get("TURSO_DATABASE_URL")
    if url:
        from api.turso import connect as _turso_connect
        return _turso_connect(url, os.environ["TURSO_AUTH_TOKEN"])
    return get_conn()


def init_tables() -> None:
    """Create API-owned tables if they don't already exist. Idempotent.

    Runs against the WRITABLE store (get_app_conn) — locally that's the main
    SQLite file; on serverless it's Turso.
    """
    conn = get_app_conn()
    try:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS student_profiles (
                id                    INTEGER PRIMARY KEY AUTOINCREMENT,
                name                  TEXT NOT NULL,
                gender                TEXT CHECK(gender IN ('M', 'F', 'Other')),
                percentile            REAL NOT NULL,
                jee_main_rank         INTEGER,
                board_pct             REAL,
                category_base         TEXT NOT NULL,
                category_variant      TEXT,
                home_district         TEXT,
                pwd_status            INTEGER NOT NULL DEFAULT 0,
                pwd_type              TEXT,
                defense_status        INTEGER NOT NULL DEFAULT 0,
                tfws_eligible         INTEGER NOT NULL DEFAULT 0,
                orphan_status         INTEGER NOT NULL DEFAULT 0,
                ews_eligible          INTEGER NOT NULL DEFAULT 0,
                family_income_bracket TEXT,
                preferred_branches    TEXT,
                preferred_locations   TEXT,
                max_fee               INTEGER,
                notes                 TEXT,
                counsellor_id         TEXT,
                created_at            TEXT NOT NULL DEFAULT (datetime('now')),
                updated_at            TEXT NOT NULL DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS student_shortlists (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                student_id      INTEGER NOT NULL
                                REFERENCES student_profiles(id) ON DELETE CASCADE,
                canonical_code  TEXT NOT NULL,
                college_name    TEXT,
                branch_name     TEXT,
                band            TEXT,
                predicted_close REAL,
                margin          REAL,
                confidence      TEXT,
                category_used   TEXT,
                seat_type       TEXT,
                fee_text        TEXT,
                branch_code     TEXT,
                college_score   REAL,
                seat_pool       TEXT,
                saved_at        TEXT NOT NULL DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS college_descriptions (
                college_code         TEXT PRIMARY KEY,
                description          TEXT NOT NULL,
                generated_at         TEXT NOT NULL DEFAULT (datetime('now')),
                edited_by_counselor  INTEGER NOT NULL DEFAULT 0
            );

            CREATE TABLE IF NOT EXISTS counselors (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                name          TEXT NOT NULL,
                email         TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                created_at    TEXT NOT NULL DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS counselor_shortlists (
                id               INTEGER PRIMARY KEY AUTOINCREMENT,
                counselor_id     INTEGER NOT NULL
                                 REFERENCES counselors(id) ON DELETE CASCADE,
                college_code     TEXT NOT NULL,
                college_name     TEXT,
                city             TEXT,
                score            REAL,
                institution_type TEXT,
                saved_at         TEXT NOT NULL DEFAULT (datetime('now')),
                UNIQUE(counselor_id, college_code)
            );
        """)

        # Idempotent column migrations for DBs created before these columns
        # existed (CREATE TABLE IF NOT EXISTS won't add columns to an existing
        # table). Each ALTER is guarded — SQLite has no ADD COLUMN IF NOT EXISTS.
        _migrations = [
            ("student_profiles", "ews_eligible", "INTEGER NOT NULL DEFAULT 0"),
            # Session 2 (DSE): 'fe' = first year (MHT-CET percentile), 'dse' =
            # direct second year (diploma lateral entry). For DSE students the
            # authoritative merit mark is diploma_pct (a diploma aggregate
            # percentage); the NOT NULL percentile column mirrors it so list
            # sorting keeps working, but engine routing reads diploma_pct.
            ("student_profiles", "admission_type", "TEXT NOT NULL DEFAULT 'fe'"),
            ("student_profiles", "diploma_pct", "REAL"),
            ("student_shortlists", "branch_code", "TEXT"),
            ("student_shortlists", "college_score", "REAL"),
            ("student_shortlists", "seat_pool", "TEXT"),
        ]
        for table, col, decl in _migrations:
            # pragma_table_info() (function form) works on both sqlite3 and libSQL
            cols = {r["name"] for r in conn.execute(
                f"SELECT name FROM pragma_table_info('{table}')")}
            if col not in cols:
                conn.execute(f"ALTER TABLE {table} ADD COLUMN {col} {decl}")

        conn.commit()
    finally:
        conn.close()
