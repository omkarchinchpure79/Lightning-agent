"""
score_colleges.py
Phase 3 — Compute 1-10 subset scores from raw college_details data.

For each college that has data in college_details, computes scores for
the 20 subsets defined in subset_definitions and writes them to
college_subset_scores. Then triggers compute_college_scores() to update
colleges.score and colleges.completeness.

Scoring rules (all deterministic, no guessing):
  naac          : A++=10, A+=9, A=7, B++=6, B+=5, B=4, C=2, None=skip
  nirf          : 1-50->10, 51-100->8, 101-150->7, 151-200->6, 201-300->5, 301+=4
  nba           : has NBA branches -> 8, else skip
  autonomous    : is_autonomous=1 -> 8, else skip
  affiliation   : always derivable from DB join -> score via university tier
  year_estd     : <=1960->10, <=1980->9, <=1990->8, <=2000->6, <=2010->5, else 4
  placement_pct : >=90->10, >=80->8, >=70->6, >=60->4, else 2
  avg_package   : >=15->10, >=10->8, >=7->6, >=5->4, else 2 (LPA)
  highest_pkg   : >=40->10, >=20->8, >=10->6, >=5->4, else 2 (LPA)
  recruiters    : has data -> 7 (manual score; can override via enter_manual_data.py)
  campus        : >=100 acres->10, >=50->8, >=25->6, >=10->4, else 2
  labs          : manual only (enter_manual_data.py)
  hostel        : boys+girls->8, boys only->6, girls only->6, none->skip
  sports        : has_sports=1 -> 6, else skip
  internet      : has_wifi=1 -> 6, else skip
  fee           : <=50k/yr->10, <=1L->8, <=1.5L->6, <=2L->4, >2L->2 (private benchmark)
  tfws          : tfws_available=1 -> 8, else skip
  scholarships  : manual only
  city_tier     : Tier1(Pune/Mumbai/Nagpur)->9, Tier2(Nashik/Aurangabad/etc)->7, else 5
  inst_type     : gov->10, aided->8, pvt->5 (base; counselor can override)

Usage:
  python scripts/score_colleges.py            # score all colleges
  python scripts/score_colleges.py --college 06006  # score one college
  python scripts/score_colleges.py --dry-run   # print scores without writing
"""

import sqlite3
import sys
import os
from setup_college_profiles import compute_college_scores

DB_PATH = "db/edupath.db"

TIER1_CITIES = {"pune", "mumbai", "nagpur", "thane", "navi mumbai"}
TIER2_CITIES = {
    "nashik", "aurangabad", "solapur", "kolhapur", "amravati",
    "nanded", "sangli", "satara", "ahmednagar", "jalgaon",
    "chhatrapati sambhajinagar", "latur", "akola"
}


def _score_naac(grade):
    if grade is None:
        return None
    g = grade.upper().strip()
    return {"A++": 10, "A+": 9, "A": 7, "B++": 6, "B+": 5, "B": 4, "C": 2}.get(g)


def _score_nirf(rank):
    if rank is None:
        return None
    if rank <= 50:   return 10
    if rank <= 100:  return 8
    if rank <= 150:  return 7
    if rank <= 200:  return 6
    if rank <= 300:  return 5
    return 4


def _score_year(year):
    if year is None:
        return None
    if year <= 1960: return 10
    if year <= 1980: return 9
    if year <= 1990: return 8
    if year <= 2000: return 6
    if year <= 2010: return 5
    return 4


def _score_placement_pct(pct):
    if pct is None:
        return None
    if pct >= 90: return 10
    if pct >= 80: return 8
    if pct >= 70: return 6
    if pct >= 60: return 4
    return 2


def _score_avg_package(lpa):
    if lpa is None:
        return None
    if lpa >= 15: return 10
    if lpa >= 10: return 8
    if lpa >= 7:  return 6
    if lpa >= 5:  return 4
    return 2


def _score_highest_package(lpa):
    if lpa is None:
        return None
    if lpa >= 40: return 10
    if lpa >= 20: return 8
    if lpa >= 10: return 6
    if lpa >= 5:  return 4
    return 2


def _score_campus(acres):
    if acres is None:
        return None
    if acres >= 100: return 10
    if acres >= 50:  return 8
    if acres >= 25:  return 6
    if acres >= 10:  return 4
    return 2


def _score_fee(min_fee):
    if min_fee is None:
        return None
    if min_fee <= 50_000:  return 10
    if min_fee <= 100_000: return 8
    if min_fee <= 150_000: return 6
    if min_fee <= 200_000: return 4
    return 2


def _score_city(city):
    if city is None:
        return None
    c = city.lower().strip()
    if c in TIER1_CITIES:
        return 9
    if c in TIER2_CITIES:
        return 7
    return 5


def _score_inst_type(itype):
    if itype is None:
        return None
    return {"gov": 10, "aided": 8, "pvt": 5}.get(itype.lower())


def compute_scores_for_college(conn, college_code, dry_run=False):
    """
    Compute all auto-scoreable subsets for one college and write to college_subset_scores.
    Returns dict of {subset_name: score} for non-None scores.
    """
    cur = conn.cursor()

    # Fetch college_details
    cur.execute("""
        SELECT cd.naac_grade, cd.naac_score, cd.nirf_rank,
               cd.nba_branches, cd.is_autonomous, cd.year_established,
               cd.institution_type, cd.placement_pct, cd.avg_package_lpa,
               cd.highest_package_lpa, cd.top_recruiters,
               cd.campus_area_acres, cd.has_hostel_boys, cd.has_hostel_girls,
               cd.has_sports, cd.has_wifi,
               cd.annual_fee_min, cd.tfws_available,
               c.city
        FROM college_details cd
        JOIN colleges c ON c.college_code = cd.college_code
        WHERE cd.college_code = ?
        LIMIT 1
    """, (college_code,))
    row = cur.fetchone()
    if not row:
        return {}

    (naac_grade, naac_score_val, nirf_rank,
     nba_branches, is_autonomous, year_estd,
     inst_type, placement_pct, avg_pkg, high_pkg,
     recruiters, campus_acres, hostel_boys, hostel_girls,
     has_sports, has_wifi, fee_min, tfws,
     city) = row

    scores = {}

    def _add(subset, score):
        if score is not None:
            scores[subset] = float(score)

    _add("naac",          _score_naac(naac_grade))
    _add("nirf",          _score_nirf(nirf_rank))
    _add("nba",           8.0 if nba_branches else None)
    _add("autonomous",    8.0 if is_autonomous else None)
    _add("year_estd",     _score_year(year_estd))
    _add("placement_pct", _score_placement_pct(placement_pct))
    _add("avg_package",   _score_avg_package(avg_pkg))
    _add("highest_package", _score_highest_package(high_pkg))
    _add("recruiters",    7.0 if recruiters else None)
    _add("campus",        _score_campus(campus_acres))
    _add("hostel",        (8.0 if (hostel_boys and hostel_girls)
                           else 6.0 if (hostel_boys or hostel_girls)
                           else None))
    _add("sports",        6.0 if has_sports else None)
    _add("internet",      6.0 if has_wifi else None)
    _add("fee",           _score_fee(fee_min))
    _add("tfws",          8.0 if tfws else None)
    _add("city_tier",     _score_city(city))
    _add("inst_type",     _score_inst_type(inst_type))

    if not dry_run and scores:
        for subset, score in scores.items():
            cur.execute("""
                INSERT INTO college_subset_scores (college_code, subset_name, score, source)
                VALUES (?, ?, ?, 'auto')
                ON CONFLICT(college_code, subset_name)
                DO UPDATE SET score = excluded.score, source = 'auto'
                WHERE source = 'auto'
            """, (college_code, subset, score))

    return scores


def run(conn, target_code=None, dry_run=False):
    cur = conn.cursor()

    if target_code:
        codes = [target_code]
    else:
        cur.execute("SELECT DISTINCT college_code FROM college_details")
        codes = [r[0] for r in cur.fetchall()]

    total_scored = 0
    total_subsets = 0
    for code in codes:
        scores = compute_scores_for_college(conn, code, dry_run=dry_run)
        if scores:
            total_scored += 1
            total_subsets += len(scores)

    if not dry_run:
        conn.commit()
        # Recompute colleges.score and colleges.completeness
        updated = compute_college_scores(conn)
        print(f"Recomputed overall scores for {updated} colleges.")

    print(f"\nSubset scores computed: {total_subsets} scores across {total_scored} colleges.")

    # Summary of coverage
    cur.execute("""
        SELECT subset_name, COUNT(*) as filled
        FROM college_subset_scores
        WHERE source = 'auto'
        GROUP BY subset_name
        ORDER BY filled DESC
    """)
    print("\nAuto-scored subsets (out of 401 colleges):")
    for r in cur.fetchall():
        print(f"  {r[0]:<20}: {r[1]:>3} colleges")


if __name__ == "__main__":
    args = sys.argv[1:]
    dry_run = "--dry-run" in args
    target = None
    if "--college" in args:
        idx = args.index("--college")
        if idx + 1 < len(args):
            target = args[idx + 1]

    if dry_run:
        print("[DRY RUN - no writes]")

    if not os.path.exists(DB_PATH):
        print(f"ERROR: {DB_PATH} not found.")
        sys.exit(1)

    conn = sqlite3.connect(DB_PATH)
    run(conn, target_code=target, dry_run=dry_run)

    # Print top colleges by score
    cur = conn.cursor()
    cur.execute("""
        SELECT c.college_name, c.city, c.score, c.completeness
        FROM colleges c
        WHERE c.score IS NOT NULL
        ORDER BY c.score DESC
        LIMIT 20
    """)
    rows = cur.fetchall()
    if rows:
        print("\nTop colleges by computed Y score:")
        for name, city, score, comp in rows:
            print(f"  {score:.2f}  ({comp:.0f}% data)  {name[:55]}  [{city}]")

    conn.close()
    print("\nDone. Run enter_manual_data.py to add placement/infra data.")
