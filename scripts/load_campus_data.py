"""
load_campus_data.py

Loads VERIFIED campus land-area (acres) into college_details.campus_area_acres.

WHY THIS EXISTS: the profile UI has a "Campus size" field, but only ~14/740
college rows carried an area. Per the project's fail-closed rule (never guess),
this file is the ONE place campus area is filled — and ONLY from an
authoritative, single-valued source per college. Aggregator sites (collegedunia,
shiksha, etc.) routinely disagree (VJTI showed 16 / 16.5 / 17 acres across three
of them), so they are NOT accepted. Each row below cites a source where the
figure is internally consistent (Wikipedia infobox + body + m^2 cross-check, or
the college's own mandatory disclosure). Colleges without such a source are left
NULL and shown as "N/A" — never guessed.

Colleges deliberately LEFT OUT because sources conflicted or were absent (do NOT
add these without an authoritative single figure):
  - PICT Pune            — no dedicated authoritative campus figure found
  - GCE Karad            — Wikipedia infobox (70 ac) contradicts its own body (40 ac)
  - GCE Chh. Sambhajinagar — no figure in any authoritative source found
  - D.J. Sanghvi         — no authoritative figure found

Identity note: like every other data script here, a figure is applied to ALL
sibling codes of the physical college (4-digit + 5-digit) via
canonical_college_key, so the profile shows it regardless of which code is
viewed. Matching is by a specific name substring (must hit only the intended
college). Idempotent.

Run standalone (safe to re-run):  python scripts/load_campus_data.py
Also invoked by the verification gate after apply_data_corrections.py.
"""
import argparse
import sqlite3

from constants import canonical_college_key

DB_PATH = "db/edupath.db"

# (name_substring, acres, source). name_substring MUST be specific enough to
# match only the intended physical college. Every figure is verified against the
# cited authoritative source; conflicting-source colleges are omitted, not guessed.
CAMPUS_AREA_ACRES = [
    ("Veermata Jijabai Technological Institute", 16.0,
     "Wikipedia infobox 'Urban 16 acres (65,000 m2)', m^2 cross-check consistent"),
    ("COEP Technological University", 36.81,
     "Wikipedia infobox 'Urban, 36.81 acres' (College of Engineering, Pune)"),
    ("Institute of Chemical Technology, Matunga", 16.0,
     "Wikipedia (ICT): infobox + Campus section both '16 acres (65,000 m2)'"),
    ("Walchand College of Engineering, Sangli", 90.0,
     "Wikipedia infobox '90 acres (36 ha)', confirmed in body twice"),
    ("Vishwakarma Institute of Technology", 7.0,
     "Wikipedia (VIT Pune) Campus section 'spread over 7 acres (28,000 m2)'"),
    ("Sardar Patel Institute of Technology", 47.0,
     "Wikipedia (SPIT) infobox 'Urban 47 acres' + Location section (Bhavan's campus, Andheri)"),
    ("K.J.Somaiya College of Engineering", 65.0,
     "Wikipedia (KJSCE): Somaiya Vidyavihar University campus, ~65 acres (shared parent campus)"),
]


def load(conn, dry_run=False):
    cur = conn.cursor()

    # Resolve every college's sibling codes once (canonical identity → codes).
    groups: dict[str, list[str]] = {}
    for code, name in cur.execute("SELECT college_code, college_name FROM colleges"):
        groups.setdefault(canonical_college_key(code, name), []).append(code)

    applied, updated_rows, missed = 0, 0, []
    for frag, acres, source in CAMPUS_AREA_ACRES:
        matches = cur.execute(
            "SELECT college_code, college_name FROM colleges WHERE college_name LIKE ?",
            (f"%{frag}%",),
        ).fetchall()
        if not matches:
            missed.append(frag)
            continue

        # Expand to all sibling codes of every matched physical college.
        target_codes = set()
        for code, name in matches:
            key = canonical_college_key(code, name)
            target_codes.update(groups.get(key, [code]))

        placeholders = ",".join("?" * len(target_codes))
        # Only rows that exist in college_details get updated; ensure a row
        # exists for each target code so the figure is not silently dropped.
        for code in target_codes:
            cur.execute(
                "INSERT OR IGNORE INTO college_details (college_code) VALUES (?)", (code,)
            )
        res = cur.execute(
            f"UPDATE college_details SET campus_area_acres = ? "
            f"WHERE college_code IN ({placeholders})",
            [acres, *target_codes],
        )
        applied += 1
        updated_rows += res.rowcount
        print(f"  {frag[:48]:48} -> {acres:>6} acres  ({len(target_codes)} code(s))  [{source[:40]}...]")

    if missed:
        print(f"\n  WARNING: {len(missed)} name substrings matched NO college (check spelling):")
        for m in missed:
            print(f"    - {m}")

    if dry_run:
        conn.rollback()
        print(f"\n[DRY RUN] Would set campus area on {applied} colleges ({updated_rows} detail rows). Rolled back.")
    else:
        conn.commit()
        total = cur.execute(
            "SELECT COUNT(*) FROM college_details WHERE campus_area_acres IS NOT NULL"
        ).fetchone()[0]
        print(f"\nApplied verified campus area to {applied} colleges ({updated_rows} detail rows).")
        print(f"college_details rows now carrying campus_area_acres: {total}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Load verified campus areas (fail-closed).")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    conn = sqlite3.connect(DB_PATH)
    print("Loading verified campus areas (authoritative single-source only)...")
    load(conn, dry_run=args.dry_run)
    conn.close()
