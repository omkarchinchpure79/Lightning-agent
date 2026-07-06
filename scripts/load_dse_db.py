"""
load_dse_db.py — Load validated DSE cutoff rows into db/edupath.db.

Input : data/processed/dse_cutoffs.json + dse_flagged.json (parse_dse_cutoffs.py)
Tables: dse_cutoffs (full reload — the JSON is the source of truth),
        flagged_reviews (DSE rows appended with seat_type='DSE' marker).

Gates applied here (fail-closed, mirroring load_db.py):
  - category must be in DSE_CATEGORY_LEGEND (parser also checks; double gate)
  - 0 <= merit_pct <= 100

NOT applied — and deliberately so: FE's impossible-percentile monotonicity
gate (constants.find_impossible_percentile_keys) assumes merit_no is a
SINGLE STATEWIDE list per category, so a worse rank should never have a much
higher percentage than its merit-number neighbourhood. Verified against
dse_cutoffs (2026-07-06): DSE merit_no is a PER-BRANCH waitlist rank —
e.g. GST 2023 R3 has real rows at merit_no 17/73 (66-79%) then jumps to
merit_no 1516 (90%), because those merit numbers belong to entirely
different branches' independent applicant pools, not one continuous state
list. Running the FE gate here flagged 17 perfectly legitimate rows as
"impossible" (confirmed by inspecting their neighbourhoods). Applying it
per-(choice_code, category) instead of per-year would fix this properly, but
each such pool is only tens-to-low-hundreds of rows — too small for the
gate's MERIT_GATE_MIN_WINDOW=50 to ever trigger, so the gate would be a
no-op there anyway. Left out rather than run a check proven wrong for this
data shape; a real quarantine mechanism for DSE-specific glitches, if ever
needed, should be designed against DSE's actual merit-numbering rules, not
copy-pasted from FE's.

COUPLING NOTE: scripts/load_db.py (the FE PDF loader) does
`DROP TABLE IF EXISTS flagged_reviews` and recreates it from ONLY the FE
flagged set — it has no knowledge of the DSE rows this script adds. If
load_db.py is ever re-run (FE raw-data reprocessing), this script MUST be
re-run afterward or the DSE portion of flagged_reviews silently disappears.
load_db.py is not part of the fast verification gate for this reason.
"""
import json
import os
import sqlite3
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from constants import DSE_CATEGORY_LEGEND, ensure_dse_tables  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(ROOT, "db", "edupath.db")
ROWS_JSON = os.path.join(ROOT, "data", "processed", "dse_cutoffs.json")
FLAGS_JSON = os.path.join(ROOT, "data", "processed", "dse_flagged.json")

DSE_FLAG_MARKER = "DSE"  # flagged_reviews.seat_type value marking DSE-plane rows


def main() -> int:
    if not os.path.exists(ROWS_JSON):
        print(f"ERROR: {ROWS_JSON} missing — run parse_dse_cutoffs.py first.")
        return 1
    with open(ROWS_JSON, encoding="utf-8") as f:
        rows = json.load(f)
    flags = []
    if os.path.exists(FLAGS_JSON):
        with open(FLAGS_JSON, encoding="utf-8") as f:
            flags = json.load(f)

    # Double gate at load time (never trust an intermediate file blindly).
    clean, gate_flags = [], []
    for r in rows:
        problems = []
        if r["category"] not in DSE_CATEGORY_LEGEND:
            problems.append(f"category '{r['category']}' not in DSE legend")
        if not (0.0 <= r["merit_pct"] <= 100.0):
            problems.append(f"merit_pct {r['merit_pct']} out of range")
        if problems:
            r["reasons"] = problems
            gate_flags.append(r)
        else:
            clean.append(r)

    conn = sqlite3.connect(DB_PATH)
    try:
        ensure_dse_tables(conn)
        conn.execute("DELETE FROM dse_cutoffs")
        conn.executemany(
            "INSERT INTO dse_cutoffs (year, round, college_code, college_name, "
            "choice_code, course_name, category, stage, merit_no, merit_pct) "
            "VALUES (?,?,?,?,?,?,?,?,?,?)",
            [(r["year"], r["round"], r["college_code"], r["college_name"],
              r["choice_code"], r["course_name"], r["category"], r["stage"],
              r["merit_no"], r["merit_pct"]) for r in clean],
        )

        # Refresh the DSE portion of the human-review queue.
        conn.execute("DELETE FROM flagged_reviews WHERE seat_type = ?", (DSE_FLAG_MARKER,))
        all_flags = flags + gate_flags
        conn.executemany(
            "INSERT INTO flagged_reviews (year, round, college_code, college_name, "
            "branch_code, branch_name, seat_type, category, stage, merit_no, "
            "percentile, is_all_india, reason) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
            [(fl.get("year"), fl.get("round"), fl.get("college_code"),
              fl.get("college_name"), fl.get("choice_code"), fl.get("course_name"),
              DSE_FLAG_MARKER, fl.get("category"),
              str(fl["stage"]) if fl.get("stage") is not None else None,
              fl.get("merit_no"), fl.get("merit_pct"), 0,
              "DSE: " + "; ".join(fl.get("reasons", ["unspecified"]))) for fl in all_flags],
        )
        conn.commit()

        n = conn.execute("SELECT COUNT(*) FROM dse_cutoffs").fetchone()[0]
        per_year = conn.execute(
            "SELECT year, round, COUNT(*) FROM dse_cutoffs GROUP BY year, round"
        ).fetchall()
        nf = conn.execute(
            "SELECT COUNT(*) FROM flagged_reviews WHERE seat_type = ?", (DSE_FLAG_MARKER,)
        ).fetchone()[0]
    finally:
        conn.close()

    print(f"dse_cutoffs loaded: {n} rows (gate-flagged: {len(gate_flags)})")
    for year, rnd, cnt in per_year:
        print(f"  {year} R{rnd}: {cnt}")
    print(f"flagged_reviews (DSE): {nf}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
