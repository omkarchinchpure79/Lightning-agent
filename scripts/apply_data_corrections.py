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
                       find_impossible_percentile_keys, normalize_district,
                       canonical_college_key)

DB_PATH = "db/edupath.db"

# Fact columns that must be a single, current truth per physical college.
# (table, column, college_data_sources.field_name-or-None)
# None means the field isn't tracked in college_data_sources (e.g. colleges.city
# comes from the CET cutoff PDFs, not the scraper) — falls straight to the
# recency tiebreak below.
RECONCILED_FACTS = (
    ("college_details", "naac_grade", "naac_grade"),
    ("college_details", "institution_type", "institution_type"),
    ("college_details", "year_established", "year_established"),
    ("colleges", "city", None),
)

# (name_substring, {column: value}, reason). name_substring must be specific
# enough to hit ONLY the intended college(s); it updates every paired code.
CORRECTIONS = [
    ("COEP Technological University",
     {"institution_type": "gov", "is_autonomous": 1},
     "COEP is a Maharashtra state government autonomous university, not private."),
    ("Institute of Chemical Technology, Matunga",
     {"institution_type": "gov", "naac_grade": "A++", "nirf_rank": 41},
     "ICT Mumbai (Matunga): state-funded deemed university (ICT Act 2013); NAAC A++ "
     "(CGPA 3.77) + NIRF Engineering #41 (2024) verified across ICT site/Wikipedia/NIRF "
     "2026-07-05 — was missing, leaving an elite institute on the data-less proxy."),
    # Walchand Sangli held CONFLICTING scraped NAAC grades across its paired codes
    # (6007='A+', 06007='C'), both wrong. Verified NAAC 'A' (CGPA 3.17, Dec 2023,
    # valid to 2028) via careers360/grokipedia/college site (2026-07-05).
    ("Walchand College of Engineering, Sangli",
     {"naac_grade": "A"},
     "Walchand Sangli verified NAAC A (CGPA 3.17, 2023) — fixes the A+/C paired-code conflict."),
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


# Official Maharashtra government district renames (Gazette notifications,
# 2023) — the OLD name is not wrong data, it's just retired. Every college
# still carrying the old name in a display/filter field gets updated to the
# current name so it isn't double-counted as a separate district from its
# own current-name self (audit 2026-07-05: this is exactly what inflated the
# homepage's district count and split "Aurangabad" colleges away from
# "Chhatrapati Sambhajinagar" colleges in filters).
RETIRED_DISTRICT_NAMES = {
    "Aurangabad": "Chhatrapati Sambhajinagar",
    "Osmanabad": "Dharashiv",
}


def rename_retired_district_names(conn, dry_run=False):
    """
    Update colleges.city and college_details.district wherever they still hold
    a retired district name, to the current official name. Idempotent —
    re-running finds nothing once applied.
    """
    cur = conn.cursor()
    total = 0
    for old, new in RETIRED_DISTRICT_NAMES.items():
        for table, column in (("colleges", "city"), ("college_details", "district")):
            count = cur.execute(
                f"SELECT COUNT(*) FROM {table} WHERE {column} = ?", (old,)
            ).fetchone()[0]
            if not count:
                continue
            print(f"  [{table}.{column}] {old!r} -> {new!r}: {count} rows")
            if not dry_run:
                cur.execute(f"UPDATE {table} SET {column} = ? WHERE {column} = ?", (new, old))
            total += count
    if not dry_run:
        conn.commit()
    print(f"\nRetired district name corrections: {total} rows"
          + (" (dry run)" if dry_run else
             ". Run populate_university_map.py to refresh university_code."))
    return total


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


def reconcile_paired_college_facts(conn, dry_run=False):
    """
    A physical college has ONE true NAAC grade, institution type, founding year,
    and city — but its data was scraped independently per college_code fragment
    (4-digit vs 5-digit, or a code that survived a name/district rename), so the
    two fragments can flatly disagree (found by audit 2026-07-04 while fixing
    college scoring: e.g. one fragment's naac_grade='C' sourced from an official
    site, the paired fragment's naac_grade='A+' with no source at all — the old
    MAX()-based score sync would silently take the more favorable, unsourced
    value). Blindly averaging or MAXing these into the quality score lets a
    scraping error inflate — or a stale value depress — a college's score.

    Resolution order per conflicting field, cheapest/most-trustworthy first:
      1. One fragment's value has an is_official=1 source in college_data_sources
         -> that wins outright (a scrape traced to the college's own site beats
         an untraceable one, regardless of which number is bigger).
      2. Neither/both are is_official, but one has ANY recorded source and the
         other has none -> the sourced one wins.
      3. Neither has any provenance:
         - For `city` ONLY: the 5-digit code's value wins. A city conflict here
           is virtually always a government district rename (e.g. Aurangabad ->
           Chhatrapati Sambhajinagar, 2023) — renames are directional, so the
           value on CET Cell's newer 5-digit-code record (2024/2025) really is
           the current name. This is a narrow, justified exception, not a
           general "newer code = correct" claim.
         - For every other field (naac_grade, institution_type, year_established):
           these are either static facts that should NEVER legitimately differ
           (year_established) or ones that can genuinely change in either
           direction (naac_grade re-accreditation) — with zero provenance on
           either side there is no honest way to pick a winner. Per this
           project's fail-closed rule, GUESSING here would risk inflating or
           deflating a real college's quality score on a coin flip, so these
           are left untouched and printed under NEEDS MANUAL REVIEW instead.
    Every resolution (and every left-unresolved conflict) is printed so nothing
    is silent. Writes the winning value to BOTH fragments so a resolved
    conflict cannot resurface on the next score_colleges.py run (which reads
    college_details fresh each time). Idempotent.
    """
    cur = conn.cursor()
    all_colleges = cur.execute("SELECT college_code, college_name FROM colleges").fetchall()
    groups = {}
    for code, name in all_colleges:
        groups.setdefault(canonical_college_key(code, name), []).append(code)

    sources = {}  # (college_code, field_name) -> (is_official, retrieved_date)
    for code, field, official, retrieved in cur.execute(
        "SELECT college_code, field_name, is_official, retrieved_date FROM college_data_sources"
    ).fetchall():
        sources[(code, field)] = (official, retrieved)

    resolved, unresolved = 0, 0
    for codes in groups.values():
        if len(codes) < 2:
            continue
        for table, column, source_field in RECONCILED_FACTS:
            ph = ",".join("?" * len(codes))
            rows = cur.execute(
                f"SELECT college_code, {column} FROM {table} "
                f"WHERE college_code IN ({ph}) AND {column} IS NOT NULL", codes).fetchall()
            values = {code: val for code, val in rows}
            if len(set(values.values())) < 2:
                continue  # no conflict (or only one fragment has a value at all)

            winner_code, why = None, None
            if source_field:
                officials = [c for c in values if sources.get((c, source_field), (0, None))[0]]
                if len(officials) == 1:
                    winner_code, why = officials[0], "is_official source"
                elif not officials:
                    sourced = [c for c in values if (c, source_field) in sources]
                    if len(sourced) == 1:
                        winner_code, why = sourced[0], "only sourced fragment"
            if winner_code is None and column == "city":
                five_digit = [c for c in values if len(c) == 5]
                if len(five_digit) == 1:
                    winner_code, why = five_digit[0], "5-digit code (district rename is directional)"

            if winner_code is None:
                print(f"  [NEEDS MANUAL REVIEW] [{table}.{column}] codes {codes}: {values}  "
                      f"-> no provenance either side, left unresolved (not guessed)")
                unresolved += 1
                continue

            winning_value = values[winner_code]
            print(f"  [{table}.{column}] codes {codes}: {values}  "
                  f"-> {winning_value!r} (from {winner_code}, {why})")
            if not dry_run:
                losers = [c for c in codes if c in values and values[c] != winning_value]
                cur.executemany(
                    f"UPDATE {table} SET {column} = ? WHERE college_code = ?",
                    [(winning_value, c) for c in losers])
            resolved += 1

    if not dry_run:
        conn.commit()
    print(f"\nPaired-code fact reconciliation: {resolved} conflicting fields resolved, "
          f"{unresolved} left for manual review" + (" (dry run)" if dry_run else "."))
    return resolved


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
    rename_retired_district_names(conn, dry_run=args.dry_run)
    fix_districts_from_official_name(conn, dry_run=args.dry_run)
    reconcile_paired_college_facts(conn, dry_run=args.dry_run)
    quarantine_impossible_percentiles(conn, dry_run=args.dry_run)
    conn.close()
