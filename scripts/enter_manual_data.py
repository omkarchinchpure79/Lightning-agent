"""
enter_manual_data.py
Phase 3 — Counselor CLI for entering college profile data manually.

Covers data that can't be scraped: placement stats, infrastructure ratings,
fee details, hostel availability, and any field the counselor knows from
first-hand experience.

All manually entered data is flagged source='manual' in college_subset_scores.
Auto-computed scores (source='auto') are never overwritten by this tool
unless the counselor explicitly chooses to override.

Usage:
  python scripts/enter_manual_data.py                   # interactive search
  python scripts/enter_manual_data.py --code 06006      # edit specific college
  python scripts/enter_manual_data.py --list            # list all colleges + completeness
  python scripts/enter_manual_data.py --summary         # show overall fill stats
"""

import sqlite3
import sys
import os
import datetime

DB_PATH = "db/edupath.db"


# ---------------------------------------------------------------------------
# Fields available for manual entry, grouped by subset
# Format: (db_column, display_label, value_type, hint)
# value_type: int | float | text | bool | score
# ---------------------------------------------------------------------------
MANUAL_FIELDS = [
    # Academic
    ("naac_grade",          "NAAC Grade",             "text",  "A++/A+/A/B++/B+/B/C"),
    ("naac_score",          "NAAC Score (out of 4)",  "float", "e.g. 3.42"),
    ("nirf_rank",           "NIRF Rank",              "int",   "National rank number"),
    ("nba_branches",        "NBA Accredited Branches","text",  "e.g. CS,CE,IT or 'Yes' or blank"),
    ("is_autonomous",       "Autonomous Status",      "bool",  "1=Yes 0=No"),
    ("year_established",    "Year Established",       "int",   "e.g. 1983"),
    # Institution
    ("institution_type",    "Institution Type",       "text",  "gov / aided / pvt"),
    ("management_name",     "Management/Trust Name",  "text",  "e.g. Sinhgad Technical Education Society"),
    # Financial
    ("annual_fee_min",      "Annual Fee Min (Rs)",    "float", "e.g. 120000"),
    ("annual_fee_max",      "Annual Fee Max (Rs)",    "float", "e.g. 180000"),
    ("tfws_available",      "TFWS Seats Available",   "bool",  "1=Yes 0=No"),
    # Infrastructure
    ("campus_area_acres",   "Campus Area (acres)",    "float", "e.g. 12.5"),
    ("has_hostel_boys",     "Boys Hostel",            "bool",  "1=Yes 0=No"),
    ("has_hostel_girls",    "Girls Hostel",           "bool",  "1=Yes 0=No"),
    ("has_sports",          "Sports Facilities",      "bool",  "1=Yes 0=No"),
    ("has_wifi",            "Wi-Fi / Smart Classrooms","bool", "1=Yes 0=No"),
    # Placements
    ("placement_pct",       "Placement % (0-100)",    "float", "e.g. 82.5"),
    ("avg_package_lpa",     "Average Package (LPA)",  "float", "e.g. 6.5"),
    ("highest_package_lpa", "Highest Package (LPA)",  "float", "e.g. 24.0"),
    ("top_recruiters",      "Top Recruiters",         "text",  "e.g. Infosys, TCS, Wipro"),
    ("placement_source",    "Placement Data Source",  "text",  "e.g. college_website / brochure"),
    # Location / media
    ("address",             "Full Address",           "text",  "e.g. FC Road, Shivajinagar, Pune"),
    ("website_url",         "College Website URL",    "text",  "e.g. https://pict.edu"),
    ("principal_name",      "Principal Name",         "text",  "e.g. Dr. A. B. Sharma"),
    ("notes",               "Counselor Notes",        "text",  "Any remarks for counselors"),
]

# Which subsets get re-scored after saving these fields
FIELD_TO_SUBSET = {
    "naac_grade":          "naac",
    "naac_score":          "naac",
    "nirf_rank":           "nirf",
    "nba_branches":        "nba",
    "is_autonomous":       "autonomous",
    "year_established":    "year_estd",
    "institution_type":    "inst_type",
    "placement_pct":       "placement_pct",
    "avg_package_lpa":     "avg_package",
    "highest_package_lpa": "highest_package",
    "top_recruiters":      "recruiters",
    "campus_area_acres":   "campus",
    "has_hostel_boys":     "hostel",
    "has_hostel_girls":    "hostel",
    "has_sports":          "sports",
    "has_wifi":            "internet",
    "annual_fee_min":      "fee",
    "tfws_available":      "tfws",
}


def _get_colleges(conn):
    cur = conn.cursor()
    cur.execute("""
        SELECT c.college_code, c.college_name, c.city, c.score, c.completeness
        FROM colleges c
        GROUP BY c.college_name
        HAVING MAX(c.college_code) = c.college_code
        ORDER BY c.college_name
    """)
    return cur.fetchall()


def _search_college(conn, query):
    cur = conn.cursor()
    q = f"%{query.lower()}%"
    cur.execute("""
        SELECT college_code, college_name, city, score, completeness
        FROM colleges
        WHERE LOWER(college_name) LIKE ? OR LOWER(city) LIKE ?
        GROUP BY college_name
        HAVING MAX(college_code) = college_code
        ORDER BY college_name
        LIMIT 20
    """, (q, q))
    return cur.fetchall()


def _get_details(conn, code):
    cur = conn.cursor()
    cur.execute("SELECT * FROM college_details WHERE college_code = ?", (code,))
    row = cur.fetchone()
    if not row:
        return {}
    cols = [d[0] for d in cur.description]
    return dict(zip(cols, row))


def _save_field(conn, code, field, raw_value, field_type):
    """Parse raw_value, write to college_details, trigger score recompute."""
    now = datetime.datetime.now().isoformat(timespec="seconds")
    cur = conn.cursor()

    # Parse
    if raw_value.strip() == "":
        value = None
    elif field_type == "int":
        try:
            value = int(raw_value.strip())
        except ValueError:
            print(f"  Invalid integer: {raw_value}")
            return False
    elif field_type == "float":
        try:
            value = float(raw_value.strip())
        except ValueError:
            print(f"  Invalid number: {raw_value}")
            return False
    elif field_type == "bool":
        v = raw_value.strip()
        if v in ("1", "yes", "y", "true"):
            value = 1
        elif v in ("0", "no", "n", "false"):
            value = 0
        else:
            print(f"  Enter 1/yes or 0/no")
            return False
    else:
        value = raw_value.strip()

    # Write to college_details
    cur.execute(f"UPDATE college_details SET {field} = ?, last_updated = ? WHERE college_code = ?",
                (value, now, code))

    # Re-trigger auto-scoring for this college
    from score_colleges import compute_scores_for_college
    from setup_college_profiles import compute_college_scores
    compute_scores_for_college(conn, code)
    compute_college_scores(conn)

    conn.commit()
    return True


def _print_current(conn, code):
    details = _get_details(conn, code)
    cur = conn.cursor()
    cur.execute("SELECT college_name, city, score, completeness FROM colleges WHERE college_code = ?", (code,))
    row = cur.fetchone()
    if not row:
        return
    name, city, score, comp = row
    print(f"\n{'='*65}")
    print(f"  {name}")
    print(f"  {city}  |  Score: {score or 'N/A'}  |  Completeness: {comp or 0:.0f}%")
    print(f"{'='*65}")

    # Show all filled fields
    filled = []
    for field, label, ftype, hint in MANUAL_FIELDS:
        val = details.get(field)
        if val is not None and val != "" and val != 0:
            filled.append(f"  {label:<30}: {val}")
    if filled:
        print("Current data:")
        for f in filled:
            print(f)
    else:
        print("  (no data entered yet)")


def _entry_loop(conn, code):
    """Interactive field-by-field entry for one college."""
    _print_current(conn, code)

    print("\nEnter field values (press Enter to skip, 'done' to finish, 'show' to refresh):\n")

    for field, label, ftype, hint in MANUAL_FIELDS:
        details = _get_details(conn, code)
        current = details.get(field)
        current_str = f" [{current}]" if current is not None else ""
        prompt = f"  {label}{current_str} ({hint}): "

        raw = input(prompt).strip()
        if raw.lower() == "done":
            break
        if raw.lower() == "show":
            _print_current(conn, code)
            continue
        if raw == "":
            continue

        ok = _save_field(conn, code, field, raw, ftype)
        if ok:
            print(f"    Saved.")

    _print_current(conn, code)
    print("\nEntry complete for this college.")


def cmd_list(conn):
    colleges = _get_colleges(conn)
    print(f"\n{'CODE':<8} {'SCORE':<7} {'COMP%':<7} {'CITY':<20} NAME")
    print("-" * 90)
    for code, name, city, score, comp in colleges:
        s = f"{score:.1f}" if score else " -- "
        c = f"{comp:.0f}%" if comp else " 0%"
        print(f"{code:<8} {s:<7} {c:<7} {str(city):<20} {name[:45]}")


def cmd_summary(conn):
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM colleges WHERE score IS NOT NULL")
    scored = cur.fetchone()[0]
    cur.execute("SELECT AVG(completeness) FROM colleges WHERE completeness IS NOT NULL")
    avg_comp = cur.fetchone()[0] or 0
    cur.execute("SELECT COUNT(*) FROM colleges")
    total = cur.fetchone()[0]
    cur.execute("SELECT COUNT(DISTINCT college_code) FROM college_subset_scores")
    has_any = cur.fetchone()[0]

    print(f"\nPhase 3 Summary")
    print(f"  Total colleges         : {total}")
    print(f"  With any score data    : {has_any}")
    print(f"  With overall Y score   : {scored}")
    print(f"  Avg completeness       : {avg_comp:.1f}%")

    cur.execute("""
        SELECT subset_name, COUNT(*) as filled, source
        FROM college_subset_scores
        GROUP BY subset_name, source
        ORDER BY subset_name, source
    """)
    print("\nSubset fill rates (auto + manual):")
    last_sub = None
    for sub, cnt, src in cur.fetchall():
        if sub != last_sub:
            print(f"  {sub:<22}", end="")
            last_sub = sub
        print(f"  {src}:{cnt}", end="")
    print()

    cur.execute("""
        SELECT c.college_name, c.city, c.score, c.completeness
        FROM colleges c
        WHERE c.score IS NOT NULL
        ORDER BY c.score DESC, c.completeness DESC
        LIMIT 10
    """)
    print("\nTop 10 colleges by Y score:")
    for name, city, score, comp in cur.fetchall():
        print(f"  {score:.2f}  {comp:.0f}%  {name[:55]}  [{city}]")


def main():
    args = sys.argv[1:]

    if not os.path.exists(DB_PATH):
        print(f"ERROR: {DB_PATH} not found. Run load_db.py first.")
        sys.exit(1)

    conn = sqlite3.connect(DB_PATH)

    if "--list" in args:
        cmd_list(conn)
        conn.close()
        return

    if "--summary" in args:
        cmd_summary(conn)
        conn.close()
        return

    # Direct college code
    if "--code" in args:
        idx = args.index("--code")
        code = args[idx + 1]
        cur = conn.cursor()
        cur.execute("SELECT college_code FROM college_details WHERE college_code = ?", (code,))
        if not cur.fetchone():
            print(f"College code {code} not found in college_details. Run collect_college_data.py first.")
            conn.close()
            return
        _entry_loop(conn, code)
        conn.close()
        return

    # Interactive search
    print("\nEduPath — College Profile Entry")
    print("Type part of a college name or city to search. Type 'quit' to exit.\n")

    while True:
        try:
            query = input("Search college: ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break

        if query.lower() in ("quit", "exit", "q"):
            break

        if query == "":
            continue

        results = _search_college(conn, query)
        if not results:
            print("  No colleges found.")
            continue

        print(f"\nFound {len(results)} college(s):")
        for i, (code, name, city, score, comp) in enumerate(results, 1):
            s = f"{score:.1f}" if score else "--"
            c = f"{comp:.0f}%" if comp else "0%"
            print(f"  [{i}] {code}  {s}/{c}  {name[:55]}  [{city}]")

        try:
            choice = input("\nEnter number to edit (or Enter to search again): ").strip()
        except (EOFError, KeyboardInterrupt):
            break

        if not choice.isdigit():
            continue

        idx = int(choice) - 1
        if 0 <= idx < len(results):
            code = results[idx][0]
            _entry_loop(conn, code)

    conn.close()
    print("Session ended.")


if __name__ == "__main__":
    main()
