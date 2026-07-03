"""
populate_university_map.py  (Phase 4 — Priority 0, data prerequisite)

Populates college_details.university_code + affiliated_university for every
college, by normalizing its (dirty) district — falling back to city — and
joining home_university_map. Without this, the preference engine CANNOT resolve
Home vs Other seats per college (the column was 0/376 before this ran).

Fail-explicit: colleges that can't be resolved are LEFT NULL and reported, never
guessed. Updates ALL paired codes (4-digit + 5-digit) for the same college name.

Run after setup_college_profiles.py. Idempotent.
Usage: python scripts/populate_university_map.py
"""

import sqlite3
import os

from constants import normalize_district

DB_PATH = "db/edupath.db"


def load_univ_map(conn):
    """district (canonical) -> (university_code, university_name)."""
    return {
        r[0]: (r[1], r[2])
        for r in conn.execute(
            "SELECT district, university_code, university_name FROM home_university_map"
        )
    }


def ensure_details_rows(conn):
    """
    Insert a stub college_details row for every college that has none, deriving
    district from colleges.city. Without a row here the preference engine's
    JOIN silently drops ALL of that college's predictions — 3 colleges (279
    prediction rows) were invisible to students because of this.
    """
    missing = conn.execute("""
        SELECT c.college_code, c.city FROM colleges c
        LEFT JOIN college_details cd ON cd.college_code = c.college_code
        WHERE cd.college_code IS NULL
    """).fetchall()
    for code, city in missing:
        district = normalize_district(None, city)
        conn.execute(
            "INSERT INTO college_details (college_code, district) VALUES (?, ?)",
            (code, district))
    if missing:
        conn.commit()
        print(f"Inserted {len(missing)} missing college_details stub rows "
              f"(colleges previously invisible to the preference engine).")
    return len(missing)


def run(conn):
    univ_map = load_univ_map(conn)

    ensure_details_rows(conn)

    rows = conn.execute("""
        SELECT cd.college_code, cd.district, c.college_name, c.city
        FROM college_details cd
        JOIN colleges c ON c.college_code = cd.college_code
    """).fetchall()

    resolved = 0
    unresolved = []
    cur = conn.cursor()

    for college_code, district, college_name, city in rows:
        canon = normalize_district(district, city)
        info = univ_map.get(canon) if canon else None
        if not info:
            unresolved.append((college_code, college_name, district, city))
            continue

        ucode, uname = info
        # Update every paired code sharing this college_name (4- and 5-digit).
        cur.execute("""
            UPDATE college_details SET university_code=?, affiliated_university=?
            WHERE college_code IN (
                SELECT c2.college_code FROM colleges c2
                WHERE c2.college_name = (
                    SELECT college_name FROM colleges WHERE college_code=?
                )
            )
        """, (ucode, uname, college_code))
        resolved += 1

    conn.commit()

    total = len(rows)
    five = conn.execute("""
        SELECT COUNT(*) FROM college_details
        WHERE LENGTH(college_code)=5 AND university_code IS NOT NULL
    """).fetchone()[0]
    five_total = conn.execute(
        "SELECT COUNT(*) FROM college_details WHERE LENGTH(college_code)=5"
    ).fetchone()[0]

    print(f"Rows processed:           {total}")
    print(f"Resolved a university:    {resolved}")
    print(f"Unresolved (left NULL):   {len(unresolved)}")
    print(f"5-digit coverage:         {five}/{five_total} "
          f"({100*five/five_total:.0f}%)")

    if unresolved:
        print("\nUnresolved colleges (need a district/city alias):")
        for code, name, dist, city in unresolved[:40]:
            print(f"  {code}  {name[:45]:45}  district={dist!r:20}  city={city!r}")

    print("\nUniversity distribution (5-digit colleges):")
    for r in conn.execute("""
        SELECT university_code, COUNT(*) FROM college_details
        WHERE LENGTH(college_code)=5 AND university_code IS NOT NULL
        GROUP BY university_code ORDER BY COUNT(*) DESC
    """):
        print(f"  {r[0]:8} {r[1]:>4}")

    return five, five_total


if __name__ == "__main__":
    if not os.path.exists(DB_PATH):
        print(f"ERROR: {DB_PATH} not found.")
        raise SystemExit(1)
    conn = sqlite3.connect(DB_PATH, timeout=30)
    conn.execute("PRAGMA journal_mode=WAL")
    run(conn)
    conn.close()
