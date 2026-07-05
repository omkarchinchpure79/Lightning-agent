"""
check_flagged.py — Review the human-review queue (flagged_reviews table).

Read-only: prints a summary by reason plus every flagged row so a human can
verify each one against the source PDF. Rows in this table were rejected by a
fail-closed validation gate and are NEVER auto-promoted to live tables
(see CLAUDE.md Data Rules).

Usage:
    python scripts/check_flagged.py            # summary + all rows
    python scripts/check_flagged.py --summary  # summary only
"""
import argparse
import os
import sqlite3

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                       "db", "edupath.db")


def main() -> None:
    parser = argparse.ArgumentParser(description="Review flagged (rejected) cutoff rows.")
    parser.add_argument("--summary", action="store_true", help="print only the per-reason summary")
    args = parser.parse_args()

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        total = conn.execute("SELECT COUNT(*) FROM flagged_reviews").fetchone()[0]
        print(f"flagged_reviews: {total} row(s) awaiting human review\n")
        if total == 0:
            print("Queue is empty — nothing to review.")
            return

        print("By reason:")
        for row in conn.execute(
            "SELECT reason, COUNT(*) AS n FROM flagged_reviews GROUP BY reason ORDER BY n DESC"
        ):
            print(f"  {row['n']:>5}  {row['reason']}")

        if args.summary:
            return

        print("\nAll flagged rows (verify each against the source PDF):")
        header = f"{'id':>4}  {'year':>4} {'rnd':>3}  {'college':<7} {'branch_code':<12} {'cat':<8} {'merit':>7} {'pct':>10}  reason"
        print(header)
        print("-" * len(header))
        for row in conn.execute(
            "SELECT id, year, round, college_code, branch_code, category, merit_no, "
            "percentile, reason FROM flagged_reviews ORDER BY year, round, college_code"
        ):
            print(
                f"{row['id']:>4}  {row['year']:>4} {row['round']:>3}  "
                f"{row['college_code'] or '':<7} {row['branch_code'] or '':<12} "
                f"{row['category'] or '':<8} {row['merit_no'] if row['merit_no'] is not None else '':>7} "
                f"{row['percentile'] if row['percentile'] is not None else '':>10}  {row['reason']}"
            )
    finally:
        conn.close()


if __name__ == "__main__":
    main()
