"""
parse_seat_intake.py

Parses the CAPR-I "Provisional Allotment List" PDFs (downloaded by
download_seat_intake_pdfs.py) for the one piece of data they carry that no
other source in this project has: per-branch sanctioned seat intake, split
into a general/EWS pool and a separately-listed TFWS pool.

Document structure (verified across autonomous, government-aided, and
university-department colleges — see conversation notes 2026-07-05):
  For each branch, a course-code header line is followed by a "Sanction
  Intake: N" line, appearing exactly ONCE per course-code variant (even when
  that branch's candidate listing spans multiple pages):
    "0303650710 - Chemical Engineering"            -> general pool
    "0303650710 [EWS] - Chemical Engineering"      -> EWS pool (supernumerary)
    "0303650711T - Chemical Engineering"           -> TFWS pool (trailing "T")
  All three course codes collapse to the SAME canonical_branch_key (verified:
  canonical_branch_key() already strips the trailing letter + seat-type digit
  pair for exactly this reason), so this aligns cleanly onto the branch
  identity predictions_2026/cutoffs already use — no new identity scheme.

Validation (fail-closed, per project convention): a college whose PDF yields
zero parsed branches, or a canonical_code with conflicting Sanction Intake
values across variants, is flagged and skipped rather than guessed.

Usage:
  python scripts/parse_seat_intake.py             # parse all + load
  python scripts/parse_seat_intake.py --dry-run    # parse + report only
"""
import argparse
import glob
import os
import re
import sqlite3

import pdfplumber

from constants import canonical_branch_key

DB_PATH = "db/edupath.db"
PDF_DIR = "data/raw/pdfs/seat_intake"
YEAR, ROUND = 2025, 1

# "0303650710 - Chemical Engineering"          groups: code=0303650710, letters='', tag=None
# "0303650710 [EWS] - Chemical Engineering"     groups: code=0303650710, letters='', tag=EWS
# "0303650711T - Chemical Engineering"         groups: code=0303650711, letters=T,  tag=None
_HEADER_RE = re.compile(
    r"^(?P<code>\d{8,14})(?P<letters>[A-Za-z]*)\s*(?:\[(?P<tag>[A-Z]+)\])?\s*-\s*(?P<branch>[^\n]+?)\s*$"
)
_INTAKE_RE = re.compile(r"Sanction Intake:\s*(\d+)")


def _classify(letters, tag):
    """
    A branch's total intake is split across several course-code sub-entries,
    each a genuinely separate reserved pool with its own Sanction Intake and
    its own admitted candidates — not alternate representations of the same
    seats. Observed sub-splits (legend: "L - Regional Language, F - Female,
    T - TFWS, U - UnAided, K - Konkan"):
      base (no letters, no tag)      -> general
      "K"/"L"/"F"/"U" (no "T")       -> general  (a regional/gender/aid quota
                                         carved out of the branch's regular
                                         capacity — still part of "general")
      "T" or combined e.g. "LT"      -> tfws     (TFWS, alone or within a
                                         regional-quota sub-pool)
      "[EWS]" tag                    -> ews      (supernumerary, own bucket —
                                         folding this into general was the
                                         bug that caused false conflicts,
                                         since EWS is a materially smaller,
                                         genuinely different number)
    Because sub-pools are additive, the caller SUMS same-bucket entries for a
    canonical branch rather than treating differing values as a conflict.
    """
    if "T" in letters.upper():
        return "tfws"
    if tag == "EWS":
        return "ews"
    return "general"


def parse_pdf(filepath, college_code, college_name):
    """
    Returns {canonical_code: {"branch_name": str, "general": int, "tfws": int, "ews": int}}
    (buckets default to 0 and are summed across sub-quota entries) plus a list
    of TRUE anomalies — the exact same course code parsed twice with two
    different Sanction Intake values, which would indicate a PDF text-extraction
    glitch, not a legitimate multi-pool branch.
    """
    parsed = {}
    seen_codes = {}  # (canonical, exact course code incl. letters+tag) -> intake, to catch real dupes
    anomalies = []
    with pdfplumber.open(filepath) as pdf:
        for page in pdf.pages:
            text = page.extract_text() or ""
            lines = text.split("\n")
            for i, line in enumerate(lines):
                m = _HEADER_RE.match(line.strip())
                if not m:
                    continue
                # The Sanction Intake line follows within the next couple of lines.
                intake = None
                for lookahead in lines[i + 1:i + 4]:
                    im = _INTAKE_RE.search(lookahead)
                    if im:
                        intake = int(im.group(1))
                        break
                if intake is None:
                    continue  # header without a parseable intake — skip, don't guess

                code = m.group("code")
                letters = m.group("letters")
                tag = m.group("tag")
                branch_name = m.group("branch").strip()
                bucket = _classify(letters, tag)
                canonical = canonical_branch_key(college_name, branch_name, code)

                exact_key = (canonical, code, letters, tag)
                if exact_key in seen_codes:
                    if seen_codes[exact_key] != intake:
                        anomalies.append((canonical, exact_key, seen_codes[exact_key], intake))
                    continue  # already counted this exact sub-pool once — a repeated header (multi-page section)
                seen_codes[exact_key] = intake

                entry = parsed.setdefault(canonical, {"branch_name": branch_name, "general": 0, "tfws": 0, "ews": 0})
                entry[bucket] += intake
    return parsed, anomalies


def run(dry_run=False):
    """branch_intake's schema lives in setup_college_profiles.py (single source
    of truth for schema, per project convention) — run that script first."""
    conn = sqlite3.connect(DB_PATH)
    if not conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='branch_intake'"
    ).fetchone():
        raise SystemExit("branch_intake table doesn't exist — run setup_college_profiles.py first.")

    files = sorted(glob.glob(os.path.join(PDF_DIR, "CAPR-I_*.pdf")))
    print(f"Parsing {len(files)} seat-intake PDFs...")

    total_branches = 0
    empty_colleges = []
    all_anomalies = []
    rows_to_insert = []

    for fp in files:
        code = os.path.basename(fp).replace("CAPR-I_", "").replace(".pdf", "")
        row = conn.execute("SELECT college_name FROM colleges WHERE college_code = ?", (code,)).fetchone()
        if not row:
            empty_colleges.append((code, "college_code not found in colleges table"))
            continue
        college_name = row[0]

        parsed, anomalies = parse_pdf(fp, code, college_name)
        if not parsed:
            empty_colleges.append((code, "zero branches parsed"))
            continue
        if anomalies:
            all_anomalies.extend((code,) + a for a in anomalies)

        for canonical, data in parsed.items():
            total_branches += 1
            rows_to_insert.append((
                canonical, code, data["branch_name"], data["general"], data["tfws"],
                YEAR, ROUND, os.path.basename(fp)
            ))

    print(f"\nParsed {total_branches} branch-intake records from {len(files) - len(empty_colleges)} colleges.")
    if empty_colleges:
        print(f"\n{len(empty_colleges)} colleges yielded NO data (flagged, not guessed):")
        for code, reason in empty_colleges[:20]:
            print(f"  {code}: {reason}")
        if len(empty_colleges) > 20:
            print(f"  ... and {len(empty_colleges) - 20} more")
    if all_anomalies:
        print(f"\n{len(all_anomalies)} exact-duplicate course codes with DIFFERING Sanction Intake "
              f"(text-extraction glitch, not a legitimate multi-pool split — flagged for review):")
        for a in all_anomalies[:20]:
            print(f"  {a}")

    if not dry_run:
        conn.executemany("""
            INSERT INTO branch_intake
                (canonical_code, college_code, branch_name, general_intake, tfws_intake, year, round, source_file)
            VALUES (?,?,?,?,?,?,?,?)
            ON CONFLICT(canonical_code) DO UPDATE SET
                college_code = excluded.college_code, branch_name = excluded.branch_name,
                general_intake = excluded.general_intake, tfws_intake = excluded.tfws_intake,
                year = excluded.year, round = excluded.round, source_file = excluded.source_file
        """, rows_to_insert)
        conn.commit()
        print(f"\nLoaded {len(rows_to_insert)} rows into branch_intake.")
    else:
        print(f"\n[DRY RUN] Would load {len(rows_to_insert)} rows.")

    conn.close()


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Parse seat-intake PDFs into branch_intake.")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    run(dry_run=args.dry_run)
