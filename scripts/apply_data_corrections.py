"""
apply_data_corrections.py

Authoritative, auditable overrides for confirmed source-data errors that the
automatic seeding (collect_college_data.py) gets wrong. Each entry is a verified
public fact, not a guess — keep this list tight and explain every row.

Why this exists separately: collect_college_data seeds institution_type via name
REGEX (GOV_PATTERNS), which misses institutes that aren't literally "government"
(COEP, ICT). And is_autonomous has NO seed source at all. This script is the one
place those confirmed corrections live, applied LAST so they always win. Run it
after collect_college_data.py. Idempotent.

Scope is deliberately narrow (user-approved 2026-06-29): the 3 confirmed errors
only. The broad is_autonomous gap (VJTI/PICT/VIT/etc. all flagged 0) is a
data-collection/ops task, NOT guessed here.
"""

import argparse
import re
import sqlite3

from constants import (CITY_TO_DISTRICT, DISTRICT_ALIASES,
                       find_impossible_percentile_keys, normalize_district)

DB_PATH = "db/edupath.db"

# (name_substring, {column: value}, reason). name_substring must be specific
# enough to hit ONLY the intended college(s); it updates every paired code.
CORRECTIONS = [
    ("COEP Technological University",
     {"institution_type": "gov", "is_autonomous": 1},
     "COEP is a Maharashtra state government autonomous university, not private."),
    ("Institute of Chemical Technology, Matunga",
     {"institution_type": "gov"},
     "ICT Mumbai (Matunga) is a state-funded deemed university (ICT Act 2013), not private."),
]


def apply(conn, dry_run=False):
    cur = conn.cursor()
    total_rows = 0
    for frag, fields, reason in CORRECTIONS:
        codes = [r[0] for r in cur.execute(
            "SELECT college_code FROM colleges WHERE college_name LIKE ?",
            (f"%{frag}%",))]
        if not codes:
            print(f"  [skip] no college matches {frag!r}")
            continue
        # Show before
        before = cur.execute(
            f"SELECT college_code, {', '.join(fields)} FROM college_details "
            f"WHERE college_code IN ({','.join('?'*len(codes))})", codes).fetchall()
        print(f"\n  {frag}  ({reason})")
        print(f"    codes: {codes}")
        print(f"    before: {before}")
        if not dry_run:
            set_sql = ", ".join(f"{c}=?" for c in fields)
            cur.execute(
                f"UPDATE college_details SET {set_sql} "
                f"WHERE college_code IN ({','.join('?'*len(codes))})",
                list(fields.values()) + codes)
            total_rows += cur.rowcount
            after = cur.execute(
                f"SELECT college_code, {', '.join(fields)} FROM college_details "
                f"WHERE college_code IN ({','.join('?'*len(codes))})", codes).fetchall()
            print(f"    after:  {after}")
    if not dry_run:
        conn.commit()
    print(f"\nApplied corrections to {total_rows} college_details rows.")
    return total_rows


def _name_location(name):
    """
    Extract the location a college's OFFICIAL CET name declares, as a canonical
    district. Indian college names put the location last ("..., Karvenagar,
    Pune"), so the LAST recognized location token wins (handles "Mumbai
    Marathwada off campus, Jalna" and "Hingoli Rd, Nanded"). Returns
    (token, canonical_district) or (None, None) if the name names no location.
    """
    loc_to_district = dict(CITY_TO_DISTRICT)
    for d in set(DISTRICT_ALIASES.values()):
        loc_to_district.setdefault(d, d)
    hits = []
    for tok in sorted(loc_to_district, key=len, reverse=True):
        pat = re.compile(r"(?<![A-Za-z])" + re.escape(tok) + r"(?![a-z])", re.I)
        for m in pat.finditer(name):
            if not any(s <= m.start() < e for s, e, _ in hits):
                hits.append((m.start(), m.end(), tok))
    if not hits:
        return None, None
    hits.sort()
    tok = hits[-1][2]
    return tok, loc_to_district[tok]


def fix_districts_from_official_name(conn, dry_run=False):
    """
    The scraped college_details.district is wrong for some colleges (the
    scraper matched a same-name campus in another city — e.g. Cummins College,
    Karvenagar, PUNE stored as NAGPUR; Sipna Amravati stored as SINDHUDURG).
    A wrong district resolves the wrong home university, which flips Home/Other
    seat eligibility for every student at that college.

    The official CET college NAME is authoritative. Where the name declares a
    location whose university differs from the stored district's university,
    trust the name: fix district (and city, for the location filter).
    Idempotent; run populate_university_map.py afterwards to refresh
    university_code.
    """
    hum = dict(conn.execute(
        "SELECT district, university_code FROM home_university_map").fetchall())
    rows = conn.execute("""
        SELECT col.college_code, col.college_name, col.city, cd.district
        FROM colleges col JOIN college_details cd USING(college_code)
        WHERE cd.district IS NOT NULL
    """).fetchall()

    fixed = 0
    for code, name, city, district in rows:
        tok, name_dist = _name_location(name)
        if not name_dist:
            continue
        stored = normalize_district(district)
        u_name, u_stored = hum.get(name_dist), hum.get(stored)
        if not u_name or not u_stored or u_name == u_stored:
            continue
        print(f"  [{code}] {name[:58]}")
        print(f"      district {district!r} -> {name_dist!r}  "
              f"(university {u_stored} -> {u_name}, from name token {tok!r})")
        if not dry_run:
            conn.execute(
                "UPDATE college_details SET district=? WHERE college_code=?",
                (name_dist, code))
            conn.execute(
                "UPDATE colleges SET city=? WHERE college_code=?",
                (name_dist, code))
        fixed += 1
    if not dry_run:
        conn.commit()
    print(f"\nDistrict-from-name corrections: {fixed} rows"
          + (" (dry run)" if dry_run else
         ". Run populate_university_map.py to refresh university_code."))
    return fixed


def quarantine_impossible_percentiles(conn, dry_run=False):
    """
    Move cutoff rows whose printed percentile is impossible for their merit
    number (CET Cell source-PDF glitch, e.g. TFWS rows printed "(0.0000000)"
    against merit 1102) from cutoffs to flagged_reviews. Same detector
    load_db.py uses at load time; this heals a DB loaded before that gate
    existed. Idempotent — already-quarantined rows are simply gone.
    """
    cur = conn.cursor()
    rows = cur.execute(
        "SELECT id, year, percentile, merit_no FROM cutoffs WHERE is_all_india = 0"
    ).fetchall()
    bad_ids = find_impossible_percentile_keys(rows)
    if not bad_ids:
        print("\nImpossible-percentile quarantine: nothing to do.")
        return 0

    detail = cur.execute(
        f"SELECT cu.id, cu.year, cu.round, col.college_code, col.college_name, "
        f"cu.branch_code, b.branch_name, cu.seat_type, cu.category, cu.stage, "
        f"cu.merit_no, cu.percentile, cu.is_all_india "
        f"FROM cutoffs cu "
        f"JOIN branches b ON b.branch_code = cu.branch_code "
        f"JOIN colleges col ON col.college_code = b.college_code "
        f"WHERE cu.id IN ({','.join('?' * len(bad_ids))})",
        sorted(bad_ids)).fetchall()

    print(f"\nImpossible-percentile quarantine: {len(detail)} cutoff rows "
          f"(percentile impossible for merit_no — source PDF glitch):")
    for d in detail[:10]:
        print(f"    {d[1]} R{d[2]} {d[8]:<8} {d[4][:40]:<42} pct={d[11]} merit={d[10]}")
    if len(detail) > 10:
        print(f"    ... and {len(detail) - 10} more")

    if not dry_run:
        cur.executemany(
            "INSERT INTO flagged_reviews (year, round, college_code, college_name, "
            "branch_code, branch_name, seat_type, category, stage, merit_no, "
            "percentile, is_all_india, reason) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
            [(d[1], d[2], d[3], d[4], d[5], d[6], d[7], d[8], d[9], d[10], d[11],
              d[12], "percentile impossible for merit_no (source PDF glitch)")
             for d in detail])
        cur.execute(
            f"DELETE FROM cutoffs WHERE id IN ({','.join('?' * len(bad_ids))})",
            sorted(bad_ids))
        conn.commit()
        print(f"  Moved to flagged_reviews and removed from cutoffs. "
              f"Re-run generate_predictions.py to refresh predictions.")
    return len(detail)


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Apply confirmed source-data corrections.")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    conn = sqlite3.connect(DB_PATH, timeout=30)
    conn.execute("PRAGMA journal_mode=WAL")
    apply(conn, dry_run=args.dry_run)
    fix_districts_from_official_name(conn, dry_run=args.dry_run)
    quarantine_impossible_percentiles(conn, dry_run=args.dry_run)
    conn.close()
