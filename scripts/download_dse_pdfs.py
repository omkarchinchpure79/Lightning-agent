"""
download_dse_pdfs.py — Download official DSE (Direct Second Year Engineering)
CAP cutoff PDFs for the 2023-24, 2024-25 and 2025-26 seasons.

Sources (verified 2026-07-06, see docs/dse_design.md):
  - AY 2025-26 : live on dse2025.mahacet.org.in (direct static PDFs).
  - AY 2024-25 : the dse2024 portal's staticFiles dir 403s server-side
                 ("Server unable to read htaccess file"), but the dse2025
                 portal republishes the same official files as previous-year
                 reference — those URLs are used here.
  - AY 2023-24 : only reachable via the Internet Archive's snapshots of the
                 official dse2023/dse2024 URLs (faithful byte copies of the
                 official CET Cell PDFs; the md5 of the 2023 R1 file matched
                 across two independent portal snapshots).

TRAP (cost us one wrong download already): the dseNNNN portal of season N
links the PREVIOUS season's cutoffs as "CAP Round - I/II/III" reference.
Never trust the URL's year — every file is verified fail-closed against the
"for AY YYYY-YY" line printed inside the PDF, plus the round number.

Public corpus note: 2023-24 published cutoffs for CAP rounds I-III;
2024-25 and 2025-26 published rounds I-II only. That is the complete set of
officially published DSE cutoff lists.
"""
import os
import re
import sys
import urllib.request

import pdfplumber

DEST_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                        "data", "raw", "pdfs", "dse")

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0 Safari/537.36")

# (year, round) -> ordered candidate URLs (first that yields a verified PDF wins)
SOURCES: dict[tuple[int, int], list[str]] = {
    (2023, 1): [
        "https://web.archive.org/web/20240511015831if_/https://dse2023.mahacet.org.in/dse23/Dse_Static_23/DSE_CAP1_CutOff_2023_24.pdf",
        "https://web.archive.org/web/20250528125834if_/https://dse2024.mahacet.org.in/dse24/staticFiles/Provisional%20Cutoff%20List%20of%20CAP%20Round%20I%20DSE.pdf",
    ],
    (2023, 2): [
        "https://web.archive.org/web/20250528125842if_/https://dse2024.mahacet.org.in/dse24/staticFiles/Provisional%20Cutoff%20List%20of%20CAP%20Round%20II%20DSE.pdf",
    ],
    (2023, 3): [
        "https://web.archive.org/web/20250528125739if_/https://dse2024.mahacet.org.in/dse24/staticFiles/Provisional%20cutoff%20List%20of%20CAP%20Round%20III%20DSE.pdf",
    ],
    (2024, 1): [
        "https://dse2025.mahacet.org.in/dse25/staticFiles/DSE_CAP_ROUND_I_CUTOFF_2024_25.pdf",
        "https://web.archive.org/web/20250706061620if_/https://dse2025.mahacet.org.in/dse25/staticFiles/DSE_CAP_ROUND_I_CUTOFF_2024_25.pdf",
    ],
    (2024, 2): [
        "https://dse2025.mahacet.org.in/dse25/staticFiles/DSE_CAP_ROUND_II_CUTOFF_2024_25.pdf",
        "https://web.archive.org/web/20250706061620if_/https://dse2025.mahacet.org.in/dse25/staticFiles/DSE_CAP_ROUND_II_CUTOFF_2024_25.pdf",
    ],
    (2025, 1): [
        "https://dse2025.mahacet.org.in/dse25/staticFiles/DSE_CAP1_CutOff_2025_26.pdf",
        "https://web.archive.org/web/20250829114536if_/https://dse2025.mahacet.org.in/dse25/staticFiles/DSE_CAP1_CutOff_2025_26.pdf",
    ],
    (2025, 2): [
        "https://dse2025.mahacet.org.in/dse25/staticFiles/dse_cap2_cut_off_2025_26.pdf",
        "https://web.archive.org/web/20250829105346if_/https://dse2025.mahacet.org.in/dse25/staticFiles/dse_cap2_cut_off_2025_26.pdf",
    ],
}

_ROMAN = {1: "I", 2: "II", 3: "III", 4: "IV"}


def dest_path(year: int, rnd: int) -> str:
    return os.path.join(DEST_DIR, f"dse_cutoff_{year}_round{rnd}.pdf")


def verify_pdf(path: str, year: int, rnd: int) -> tuple[bool, str]:
    """Fail-closed content check: page 1 must carry the expected AY and round.

    The portals link previous seasons' files under current-season URLs, so the
    filename/URL is NEVER trusted — only the header printed inside the PDF.
    """
    ay = f"AY {year}-{str(year + 1)[2:]}"          # e.g. "AY 2023-24"
    round_pat = rf"CAP\s+Round\s+{_ROMAN[rnd]}\b"
    try:
        with pdfplumber.open(path) as pdf:
            text = pdf.pages[0].extract_text() or ""
    except Exception as e:                          # noqa: BLE001 — any parse failure = reject
        return False, f"unreadable PDF ({e})"
    if ay not in text:
        return False, f"expected '{ay}' not found on page 1"
    if not re.search(round_pat, text, re.IGNORECASE):
        return False, f"expected 'CAP Round {_ROMAN[rnd]}' not found on page 1"
    return True, "ok"


def download(url: str, path: str) -> bool:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            data = r.read()
    except Exception as e:                          # noqa: BLE001
        print(f"    fetch failed: {type(e).__name__}: {e}")
        return False
    if data[:5] != b"%PDF-":
        print(f"    not a PDF (got {data[:40]!r})")
        return False
    with open(path, "wb") as f:
        f.write(data)
    return True


def main() -> int:
    os.makedirs(DEST_DIR, exist_ok=True)
    failures = []
    for (year, rnd), urls in sorted(SOURCES.items()):
        path = dest_path(year, rnd)
        if os.path.exists(path):
            ok, why = verify_pdf(path, year, rnd)
            if ok:
                print(f"AY {year}-{str(year+1)[2:]} R{rnd}: already present, verified.")
                continue
            print(f"AY {year}-{str(year+1)[2:]} R{rnd}: existing file FAILS check ({why}) — re-downloading.")
            os.remove(path)
        got = False
        for url in urls:
            print(f"AY {year}-{str(year+1)[2:]} R{rnd}: fetching {url[:90]}...")
            if not download(url, path):
                continue
            ok, why = verify_pdf(path, year, rnd)
            if ok:
                print(f"    OK ({os.path.getsize(path):,} bytes, header verified)")
                got = True
                break
            print(f"    REJECTED: {why} — deleting.")
            os.remove(path)
        if not got:
            failures.append((year, rnd))
    if failures:
        print("\nFAILED (no verified source):", failures)
        return 1
    print("\nAll DSE cutoff PDFs present and header-verified.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
