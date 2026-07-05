"""
download_seat_intake_pdfs.py

Downloads the official CET Cell "Provisional Allotment List" PDF (CAPR-I) for
every college with 2025 Round-1 cutoff data. This document type is DIFFERENT
from the cutoff PDFs already in data/raw/pdfs/ — it's a per-college document
that lists, for every branch, a "Sanction Intake: N" line (the branch's total
sanctioned seats) split into separate course-code sub-entries for the base
pool, EWS, and TFWS ("...T" suffix course code) — exactly the seat-intake data
CLAUDE.md's Phase 4/5 UI needs and never had a source for before.

URL pattern (verified against several known college codes, including a
RECODED_COLLEGES college using its current 5-digit code, e.g. COEP=16006):
    https://fe2025.mahacet.org/CAP-I/CAPR-I_{college_code}.pdf

Only Round 1 is downloaded: sanctioned intake is a fixed institutional
capacity number, not a per-round consumption figure, so Round 1 (the first
published seat matrix) is the correct and only source needed.

Usage:
  python scripts/download_seat_intake_pdfs.py            # download all
  python scripts/download_seat_intake_pdfs.py --limit 5   # smoke test
"""
import argparse
import os
import ssl
import sqlite3
import time
import urllib.request

DB_PATH = "db/edupath.db"
OUTPUT_DIR = "data/raw/pdfs/seat_intake"
URL_TEMPLATE = "https://fe2025.mahacet.org/CAP-I/CAPR-I_{code}.pdf"

SSL_CONTEXT = ssl._create_unverified_context()
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}


def target_college_codes(conn):
    """Every college with 2025 Round-1 cutoff data — the current, CAP-active set."""
    rows = conn.execute("""
        SELECT DISTINCT b.college_code
        FROM cutoffs cu JOIN branches b ON cu.branch_code = b.branch_code
        WHERE cu.year = 2025 AND cu.round = 1
        ORDER BY b.college_code
    """).fetchall()
    return [r[0] for r in rows]


def download_one(code, retries=2):
    filepath = os.path.join(OUTPUT_DIR, f"CAPR-I_{code}.pdf")
    if os.path.exists(filepath):
        return "skip"
    url = URL_TEMPLATE.format(code=code)
    last_err = None
    for attempt in range(retries + 1):
        try:
            req = urllib.request.Request(url, headers=HEADERS)
            with urllib.request.urlopen(req, context=SSL_CONTEXT, timeout=30) as resp:
                data = resp.read()
            if not data.startswith(b"%PDF-"):
                return f"not-a-pdf ({data[:30]!r})"
            with open(filepath, "wb") as f:
                f.write(data)
            return "ok"
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return "404"
            last_err = str(e)
        except Exception as e:
            last_err = str(e)
        time.sleep(1)
    return f"error: {last_err}"


def main():
    ap = argparse.ArgumentParser(description="Download CAPR-I seat-intake PDFs for all colleges.")
    ap.add_argument("--limit", type=int, default=None, help="Only download the first N (smoke test)")
    args = ap.parse_args()

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    codes = target_college_codes(conn)
    conn.close()
    if args.limit:
        codes = codes[:args.limit]

    print(f"Downloading seat-intake PDFs for {len(codes)} colleges...")
    counts = {}
    failed = []
    for i, code in enumerate(codes, 1):
        status = download_one(code)
        counts[status.split(":")[0].split(" ")[0]] = counts.get(status.split(":")[0].split(" ")[0], 0) + 1
        if status not in ("ok", "skip"):
            failed.append((code, status))
        if i % 25 == 0 or i == len(codes):
            print(f"  [{i}/{len(codes)}] {counts}")
        time.sleep(0.15)  # polite pacing — same server hosts the cutoff PDFs too

    print(f"\nDone. {counts}")
    if failed:
        print(f"\n{len(failed)} colleges failed (no seat-intake PDF available or download error):")
        for code, status in failed[:30]:
            print(f"  {code}: {status}")
        if len(failed) > 30:
            print(f"  ... and {len(failed) - 30} more")


if __name__ == "__main__":
    main()
