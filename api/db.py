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

DB_PATH = os.path.join(_ROOT, "db", "edupath.db")


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


def get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_tables() -> None:
    """Create API-owned tables if they don't already exist. Idempotent."""
    conn = get_conn()
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
        conn.commit()
    finally:
        conn.close()
