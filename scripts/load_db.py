import sqlite3
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from constants import find_impossible_percentile_keys
from parse_cutoffs import _VALID_CATEGORY_RE

DB_PATH = "db/edupath.db"
VALID_JSON_PATH = "data/processed/cutoffs.json"
FLAGGED_JSON_PATH = "data/flagged/flagged_reviews.json"


def init_db(conn):
    cursor = conn.cursor()

    cursor.execute("PRAGMA foreign_keys = OFF;")
    cursor.execute("DROP TABLE IF EXISTS flagged_reviews;")
    cursor.execute("DROP TABLE IF EXISTS cutoffs;")
    cursor.execute("DROP TABLE IF EXISTS branches;")
    cursor.execute("DROP TABLE IF EXISTS colleges;")
    cursor.execute("PRAGMA foreign_keys = ON;")

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS colleges (
        college_code  TEXT PRIMARY KEY,
        college_name  TEXT NOT NULL,
        status        TEXT,
        city          TEXT,
        score         REAL,
        completeness  REAL
    );
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS branches (
        branch_code  TEXT PRIMARY KEY,
        college_code TEXT NOT NULL,
        branch_name  TEXT NOT NULL,
        FOREIGN KEY (college_code) REFERENCES colleges(college_code)
    );
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS cutoffs (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        year        INTEGER NOT NULL,
        round       INTEGER NOT NULL,
        seat_type   TEXT NOT NULL,
        category    TEXT NOT NULL,
        stage       TEXT NOT NULL,
        merit_no    INTEGER,
        percentile  REAL NOT NULL,
        branch_code TEXT NOT NULL,
        is_all_india INTEGER NOT NULL,
        exam_type   TEXT NOT NULL DEFAULT 'MHT-CET',
        FOREIGN KEY (branch_code) REFERENCES branches(branch_code)
    );
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS flagged_reviews (
        id           INTEGER PRIMARY KEY AUTOINCREMENT,
        year         INTEGER,
        round        INTEGER,
        college_code TEXT,
        college_name TEXT,
        branch_code  TEXT,
        branch_name  TEXT,
        seat_type    TEXT,
        category     TEXT,
        stage        TEXT,
        merit_no     INTEGER,
        percentile   REAL,
        is_all_india INTEGER,
        reason       TEXT
    );
    """)

    # Indexes for fast prediction queries (category + round + is_all_india is the hot path)
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_cutoffs_filter ON cutoffs(category, round, is_all_india);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_cutoffs_year   ON cutoffs(year);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_branches_college ON branches(college_code);")

    conn.commit()
    print("Database tables and indexes initialized.")


def load_data():
    if not os.path.exists(VALID_JSON_PATH):
        print(f"ERROR: {VALID_JSON_PATH} not found. Run parse_cutoffs.py first.")
        return False

    print(f"Loading valid records from {VALID_JSON_PATH}...")
    with open(VALID_JSON_PATH, "r") as f:
        valid_records = json.load(f)

    flagged_records = []
    if os.path.exists(FLAGGED_JSON_PATH):
        print(f"Loading flagged records from {FLAGGED_JSON_PATH}...")
        with open(FLAGGED_JSON_PATH, "r") as f:
            flagged_records = json.load(f)

    print(f"Connecting to SQLite database: {DB_PATH}")
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA journal_mode=WAL")
    init_db(conn)

    cursor = conn.cursor()

    # 1. Unique colleges — prefer the longest (most complete) name per college_code
    college_names = {}
    for rec in valid_records:
        code = rec["college_code"]
        name = rec["college_name"].strip()
        if code not in college_names or len(name) > len(college_names[code]):
            college_names[code] = name

    print(f"Inserting {len(college_names)} unique colleges...")
    for code, name in college_names.items():
        city = None
        for possible_city in [
            "Pune", "Mumbai", "Nagpur", "Amravati", "Nashik",
            "Chhatrapati Sambhajinagar", "Aurangabad",
            "Sangli", "Kolhapur", "Nanded", "Thane", "Jalgaon", "Solapur",
            "Latur", "Akola", "Yavatmal", "Wardha", "Chandrapur",
            "Dhule", "Nandurbar", "Gondia", "Bhandara", "Gadchiroli",
            "Washim", "Buldhana", "Hingoli", "Parbhani", "Beed",
            "Osmanabad", "Dharashiv", "Raigad", "Ratnagiri", "Sindhudurg",
            "Palghar", "Satara", "Ahmednagar", "Jalna",
        ]:
            if possible_city.lower() in name.lower():
                city = possible_city
                break

        cursor.execute("""
        INSERT OR REPLACE INTO colleges (college_code, college_name, status, city, score, completeness)
        VALUES (?, ?, NULL, ?, NULL, NULL)
        """, (code, name, city))

    # 2. Unique branches
    branch_names = {}
    for rec in valid_records:
        code         = rec["branch_code"]
        college_code = rec["college_code"]
        name         = rec["branch_name"].strip()
        if code not in branch_names or len(name) > len(branch_names[code][1]):
            branch_names[code] = (college_code, name)

    print(f"Inserting {len(branch_names)} unique branches...")
    for code, (college_code, name) in branch_names.items():
        cursor.execute("""
        INSERT OR REPLACE INTO branches (branch_code, college_code, branch_name)
        VALUES (?, ?, ?)
        """, (code, college_code, name))

    # 3. Cutoff records — reject parser artifacts: space-containing category codes,
    # or (parse_cutoffs.py's validate_record gate, applied again here so already-
    # generated cutoffs.json from before this check existed still gets cleaned
    # without a full re-parse) a category that isn't a real CAP code at all —
    # e.g. a table-alignment misfire on a dense category grid (2019 CAP2's
    # combined Home+PWD blocks) can leave category as a stray single letter
    # while the real category list ends up concatenated into seat_type instead.
    clean_records = [r for r in valid_records
                     if " " not in r["category"] and _VALID_CATEGORY_RE.match(r["category"])]
    skipped = len(valid_records) - len(clean_records)
    if skipped:
        print(f"Skipping {skipped} records with invalid/garbled category codes (parser artifacts).")

    # 3b. Source-PDF glitch gate: percentile impossibly low for the merit number
    # (e.g. official PDF prints "(0.0000000)" against merit 1102). Fail-closed:
    # violators go to flagged_reviews, never into cutoffs.
    mh_rows = [(i, r["year"], r["percentile"], r["merit_no"])
               for i, r in enumerate(clean_records) if not r["is_all_india"]]
    bad_idx = find_impossible_percentile_keys(mh_rows)
    if bad_idx:
        print(f"Flagging {len(bad_idx)} records whose percentile is impossible "
              f"for their merit number (source-PDF glitch) -> flagged_reviews.")
        for i in sorted(bad_idx):
            r = dict(clean_records[i])
            r["reason"] = "percentile impossible for merit_no (source PDF glitch)"
            flagged_records.append(r)
        clean_records = [r for i, r in enumerate(clean_records) if i not in bad_idx]

    print(f"Inserting {len(clean_records)} cutoff records...")

    cursor.executemany("""
    INSERT INTO cutoffs (year, round, seat_type, category, stage, merit_no, percentile, branch_code, is_all_india, exam_type)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, [
        (r["year"], r["round"], r["seat_type"], r["category"], r["stage"],
         r["merit_no"], r["percentile"], r["branch_code"], r["is_all_india"],
         r.get("exam_type", "MHT-CET"))
        for r in clean_records
    ])

    # 4. Flagged reviews
    if flagged_records:
        print(f"Inserting {len(flagged_records)} flagged review records...")
        cursor.executemany("""
        INSERT INTO flagged_reviews
            (year, round, college_code, college_name, branch_code, branch_name,
             seat_type, category, stage, merit_no, percentile, is_all_india, reason)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, [
            (r.get("year"), r.get("round"), r.get("college_code"), r.get("college_name"),
             r.get("branch_code"), r.get("branch_name"), r.get("seat_type"), r.get("category"),
             r.get("stage"), r.get("merit_no"), r.get("percentile"), r.get("is_all_india"),
             r.get("reason"))
            for r in flagged_records
        ])

    conn.commit()

    # 5. Restore Y-set scores from college_subset_scores (survives table drop — separate table)
    try:
        cursor.execute("""
            UPDATE colleges SET
                score = (
                    SELECT ROUND(AVG(css.score), 2)
                    FROM college_subset_scores css
                    WHERE css.college_code = colleges.college_code
                ),
                completeness = (
                    SELECT ROUND(COUNT(css.score) * 100.0 /
                        (SELECT COUNT(*) FROM subset_definitions), 1)
                    FROM college_subset_scores css
                    WHERE css.college_code = colleges.college_code
                )
            WHERE EXISTS (
                SELECT 1 FROM college_subset_scores css
                WHERE css.college_code = colleges.college_code
            )
        """)
        restored = cursor.rowcount
        if restored:
            print(f"  Y-set scores restored for {restored} colleges from college_subset_scores.")
        conn.commit()
    except sqlite3.OperationalError:
        pass  # college_subset_scores doesn't exist yet on first-time setup

    # 6. Summary
    cursor.execute("SELECT COUNT(*) FROM colleges;")
    col_count = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM branches;")
    br_count = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM cutoffs;")
    cut_count = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM flagged_reviews;")
    flag_count = cursor.fetchone()[0]

    print("\n" + "=" * 50)
    print("DATABASE LOAD COMPLETE:")
    print(f"  Colleges : {col_count}")
    print(f"  Branches : {br_count}")
    print(f"  Cutoffs  : {cut_count}")
    print(f"  Flagged  : {flag_count}")
    print("=" * 50)
    print("\nNOTE: Run `python scripts/generate_predictions.py` to refresh 2026 predictions.")

    conn.close()
    return True


if __name__ == "__main__":
    load_data()
