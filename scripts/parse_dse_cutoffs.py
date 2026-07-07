"""
parse_dse_cutoffs.py — Parse official DSE (Direct Second Year Engineering) CAP
cutoff PDFs into structured rows, with fail-closed validation.

Input : data/raw/pdfs/dse/dse_cutoff_{year}_round{n}.pdf  (download_dse_pdfs.py)
Output: data/processed/dse_cutoffs.json     (validated rows)
        data/processed/dse_flagged.json     (rows/blocks that failed validation)

DSE PDF layout (one consolidated statewide PDF per round):

    1012 Government College of Engineering,Yavatmal (Government)
    Choice Code : 101229310 Course Name : Electrical Engineering
    PWDR-OBC GOPEN GSC ... EWS          <- category header (column positions!)
    29618 5821 11289 ...                <- Stage-I merit numbers
    Stage-I
    (76.39%) (88.22%) ...               <- Stage-I closing DIPLOMA PERCENTAGES
    32963                               <- Stage-II merit (only columns that
    Stage-II                               closed at stage II)
    (75.00%)

CRITICAL: stage rows are COLUMN-ALIGNED to the category header, not
sequential — a stage row may cover any subset of the categories (verified:
GCOE Yavatmal Electrical 2025 R1, where LST closed at Stage-II while the
other 10 categories closed at Stage-I). Values are therefore assigned to
categories by x-coordinate, never by reading order. A value that does not
align cleanly with exactly one category column flags the whole block.

The value is a diploma aggregate PERCENTAGE (marks), NOT an MHT-CET
percentile. It lives in its own dse_cutoffs table and must never be mixed
with the FE `cutoffs` table.

Usage:
    python scripts/parse_dse_cutoffs.py             # parse + validate all 7 PDFs
    python scripts/parse_dse_cutoffs.py --discover  # print category-token census
                                                     # (legend maintenance aid)
"""
import argparse
import json
import os
import re
import sys
from collections import Counter

import pdfplumber

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from constants import DSE_CATEGORY_LEGEND  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PDF_DIR = os.path.join(ROOT, "data", "raw", "pdfs", "dse")
OUT_ROWS = os.path.join(ROOT, "data", "processed", "dse_cutoffs.json")
OUT_FLAGS = os.path.join(ROOT, "data", "processed", "dse_flagged.json")

PDFS = [
    (2023, 1), (2023, 2), (2023, 3),
    (2024, 1), (2024, 2),
    (2025, 1), (2025, 2),
]

RE_COLLEGE = re.compile(r"^\d{4,5}$")
# 1-char suffixes are real: PWD-O (PwD-Open), DEF-O (Defence-Open).
RE_CAT = re.compile(r"^[A-Z]{2,8}(?:-[A-Z]{1,8})?$")
# Merit numbers may carry a trailing 'A' marker in round-2/3 PDFs.
RE_MERIT = re.compile(r"^(\d{1,6})A?$")
RE_STAGE = re.compile(r"^Stage-(.+)$")
RE_PCT = re.compile(r"^\((\d{1,3}(?:\.\d+)?)%\)$")

HEADER_SNIPPETS = (
    "GOVERNMENT OF MAHARASHTRA", "State Common Entrance Test",
    "Address :", "Provisional", "Published On", "Under Graduate",
    "L - Ladies", "STATE CET CELL", "Page ",
    "General Merit Number", "Figures in Bracket",
)

# Category columns are ~51pt apart; a value must sit within this distance of
# exactly one category centre or the block is flagged (never guessed).
COLUMN_TOLERANCE = 22.0


def cluster_lines(words, tol=3.0):
    """Group pdfplumber words into visual lines by their top coordinate."""
    lines = []
    for w in sorted(words, key=lambda w: (w["top"], w["x0"])):
        if lines and abs(w["top"] - lines[-1][0]["top"]) <= tol:
            lines[-1].append(w)
        else:
            lines.append([w])
    return lines


def line_text(line):
    return " ".join(w["text"] for w in line)


def classify(line):
    """Classify a visual line. Order matters: college before category (an
    all-caps college name would otherwise look like category tokens).
    Stage labels are matched loosely ('Stage-I', 'Stage-VII', 'Stage-MI',
    'I-Non PWD / DEF') — the dispatcher additionally treats ANY line arriving
    between a merit line and its pct line as the stage label, because CET
    Cell's stage naming is not a closed set."""
    texts = [w["text"] for w in line]
    joined = line_text(line)
    if any(s in joined for s in HEADER_SNIPPETS):
        return "noise"
    if RE_COLLEGE.match(texts[0]) and len(texts) > 1 and not RE_MERIT.match(texts[1]):
        return "college"
    if joined.startswith("Choice Code"):
        return "choice"
    if RE_STAGE.match(joined):
        return "stage"
    if all(RE_PCT.match(t) for t in texts):
        return "pct"
    if all(RE_MERIT.match(t) for t in texts):
        return "merit"
    if all(RE_CAT.match(t) for t in texts):
        return "category"
    return "other"


def centers(line):
    return [(w["x0"] + w["x1"]) / 2.0 for w in line]


def nearest_column(x, cat_centers):
    """Index of the category column x belongs to, or None if ambiguous/too far."""
    best_i, best_d = None, None
    for i, c in enumerate(cat_centers):
        d = abs(x - c)
        if best_d is None or d < best_d:
            best_i, best_d = i, d
    if best_d is None or best_d > COLUMN_TOLERANCE:
        return None
    return best_i


class Block:
    """One (college, choice code) cutoff block being assembled."""

    def __init__(self, year, rnd, college_code, college_name):
        self.year = year
        self.round = rnd
        self.college_code = college_code
        self.college_name = college_name
        self.choice_code = None
        self.course_name = None
        self.cats = []          # [(token, x_center)]
        self.pending_merits = None   # merit line awaiting its stage + pct
        self.stage = None       # stage LABEL text, e.g. "I", "VII", "MI", "I-Non PWD / DEF"
        self.values = []        # [(category, stage_label, merit, pct)]
        self.problems = []

    def flag(self, why):
        self.problems.append(why)

    def assign(self, line, kind):
        """Column-align one merit or pct line to the category header."""
        cat_centers = [c for _, c in self.cats]
        out = {}
        for w in line:
            x = (w["x0"] + w["x1"]) / 2.0
            i = nearest_column(x, cat_centers)
            if i is None:
                self.flag(f"{kind} value '{w['text']}' aligns with no category column")
                return None
            if i in out:
                self.flag(f"two {kind} values align to category '{self.cats[i][0]}'")
                return None
            out[i] = w["text"]
        return out

    def close_stage(self, pct_line):
        """Pair the pending merit line with this pct line for the current stage."""
        if self.pending_merits is None or self.stage is None:
            self.flag("pct line without a preceding merit+stage line")
            return
        merits = self.assign(self.pending_merits, "merit")
        pcts = self.assign(pct_line, "pct")
        self.pending_merits = None
        stage, self.stage = self.stage, None
        if merits is None or pcts is None:
            return
        if set(merits) != set(pcts):
            self.flag(f"stage {stage}: merit columns {sorted(merits)} != pct columns {sorted(pcts)}")
            return
        for i in sorted(merits):
            cat = self.cats[i][0]
            pct = float(RE_PCT.match(pcts[i]).group(1))
            merit = int(RE_MERIT.match(merits[i]).group(1))  # strips 'A' marker
            self.values.append((cat, stage, merit, pct))

    def finish(self, legend):
        """Final validation. Returns (rows, flags)."""
        rows, flags = [], []
        if self.pending_merits is not None:
            self.flag("block ended with an unpaired merit line")
        if self.choice_code is None:
            self.flag("no choice code found")
        elif not self.choice_code.startswith(self.college_code):
            self.flag(f"choice code {self.choice_code} does not start with college code {self.college_code}")
        if not self.cats:
            self.flag("no category header found")
        covered = {c for c, _, _, _ in self.values}
        for cat, _ in self.cats:
            if cat not in covered:
                self.flag(f"category '{cat}' printed in header but no value found in any stage")
        for cat, stage, merit, pct in self.values:
            problems = list(self.problems)
            if legend is not None and cat not in legend:
                problems.append(f"category '{cat}' not in DSE legend")
            if not 0.0 <= pct <= 100.0:
                problems.append(f"percentage {pct} out of range")
            row = {
                "year": self.year, "round": self.round,
                "college_code": self.college_code, "college_name": self.college_name,
                "choice_code": self.choice_code, "course_name": self.course_name,
                "category": cat, "stage": stage,
                "merit_no": merit, "merit_pct": pct,
            }
            if problems:
                row["reasons"] = problems
                flags.append(row)
            else:
                rows.append(row)
        if not self.values and (self.cats or self.choice_code):
            flags.append({
                "year": self.year, "round": self.round,
                "college_code": self.college_code, "college_name": self.college_name,
                "choice_code": self.choice_code, "course_name": self.course_name,
                "category": None, "stage": None, "merit_no": None, "merit_pct": None,
                "reasons": self.problems or ["block produced no values"],
            })
        return rows, flags


def parse_choice_line(line):
    """'Choice Code : 101229110 Course Name : Civil Engineering' -> (code, name).

    The digit code can carry a trailing seat-sub-type letter (observed: F, U, L
    — e.g. '303524550F' at a women's-university-managed college), the same
    variant-suffix pattern FE branch codes use (K/L/LK/U/F). Kept verbatim in
    choice_code; constants.canonical_branch_key() strips it for identity.
    """
    m = re.match(r"Choice Code\s*:\s*(\d+[A-Z]*)\s+Course Name\s*:\s*(.*)$", line_text(line))
    if not m:
        return None, None
    return m.group(1), m.group(2).strip()


def parse_pdf(year, rnd, legend, census=None):
    path = os.path.join(PDF_DIR, f"dse_cutoff_{year}_round{rnd}.pdf")
    rows, flags = [], []
    with pdfplumber.open(path) as pdf:
        for page in pdf.pages:
            block = None
            college_code = college_name = None
            # A course name occasionally wraps onto its own line BEFORE the
            # "Choice Code :" line (observed: "VLSI" on its own line ahead of
            # "Choice Code : ... Course Name :" with an empty tail) — stash it
            # and prepend to the next choice line's course name rather than
            # flagging a spurious orphan-category error. Genuine single-category
            # headers ("GOPEN" alone) are common (465/7679 blocks sampled), so
            # this is ONLY recognised via 1-line lookahead: a lone token counts
            # as a wrapped title fragment exclusively when the very next line
            # is a "Choice Code" line — a real header is always followed by a
            # merit-number line instead.
            pending_title_prefix = None
            lines = cluster_lines(page.extract_words())
            for idx, line in enumerate(lines):
                kind = classify(line)
                if kind == "noise":
                    continue
                if kind == "category" and len(line) == 1:
                    nxt = lines[idx + 1] if idx + 1 < len(lines) else None
                    if nxt is not None and classify(nxt) == "choice":
                        if block is not None:
                            r, f = block.finish(legend)
                            rows.extend(r)
                            flags.extend(f)
                            block = None
                        pending_title_prefix = line[0]["text"]
                        continue
                if kind == "college":
                    texts = [w["text"] for w in line]
                    college_code = texts[0]
                    college_name = " ".join(texts[1:])
                    continue
                if kind == "choice":
                    if block is not None:
                        r, f = block.finish(legend)
                        rows.extend(r)
                        flags.extend(f)
                    if college_code is None:
                        flags.append({"year": year, "round": rnd, "college_code": None,
                                      "college_name": None, "choice_code": None,
                                      "course_name": line_text(line), "category": None,
                                      "stage": None, "merit_no": None, "merit_pct": None,
                                      "reasons": ["choice line before any college line"]})
                        block = None
                        continue
                    block = Block(year, rnd, college_code, college_name)
                    block.choice_code, block.course_name = parse_choice_line(line)
                    if pending_title_prefix is not None:
                        block.course_name = (
                            f"{pending_title_prefix} {block.course_name}".strip()
                            if block.course_name else pending_title_prefix)
                        pending_title_prefix = None
                    continue
                if block is None:
                    # A stage/merit/pct/category line with no open block would mean
                    # a block split across a page boundary (never observed; fail-closed).
                    if kind in ("stage", "merit", "pct", "category"):
                        flags.append({"year": year, "round": rnd, "college_code": college_code,
                                      "college_name": college_name, "choice_code": None,
                                      "course_name": None, "category": None, "stage": None,
                                      "merit_no": None, "merit_pct": None,
                                      "reasons": [f"orphan {kind} line outside any block: '{line_text(line)[:60]}'"]})
                    continue
                # A merit line is waiting: whatever non-value line comes next
                # is its stage label ("Stage-I", "Stage-MI", "I-Non PWD / DEF",
                # ...) — CET Cell's stage naming is not a closed set, so the
                # label is taken verbatim (minus any "Stage-" prefix), never
                # matched against a hardcoded list.
                if block.pending_merits is not None and kind in ("stage", "other", "category"):
                    label = line_text(line)
                    m = RE_STAGE.match(label)
                    block.stage = (m.group(1) if m else label).strip()
                    continue
                if kind == "category":
                    if block.cats:
                        block.flag("second category header line in one block (wrapped header?)")
                    block.cats = list(zip([w["text"] for w in line], centers(line)))
                    if census is not None:
                        census.update(w["text"] for w in line)
                    continue
                if kind == "merit":
                    if block.pending_merits is not None:
                        block.flag("two merit lines without a pct line between them")
                    block.pending_merits = line
                    continue
                if kind == "stage":
                    block.flag(f"stage label '{line_text(line)}' without a merit line before it")
                    continue
                if kind == "pct":
                    block.close_stage(line)
                    continue
                if kind == "other":
                    # Wrapped course name continuation (mixed-case text right
                    # after the choice line, before any categories/values).
                    if block.course_name is not None and not block.cats:
                        block.course_name += " " + line_text(line)
                    else:
                        block.flag(f"unrecognised line inside block: '{line_text(line)[:60]}'")
            if block is not None:
                r, f = block.finish(legend)
                rows.extend(r)
                flags.extend(f)
    return rows, flags


def main():
    ap = argparse.ArgumentParser(description="Parse DSE cutoff PDFs (fail-closed).")
    ap.add_argument("--discover", action="store_true",
                    help="skip legend check; print the category-token census")
    args = ap.parse_args()

    legend = None if args.discover else set(DSE_CATEGORY_LEGEND)
    census = Counter() if args.discover else None

    all_rows, all_flags = [], []
    for year, rnd in PDFS:
        rows, flags = parse_pdf(year, rnd, legend, census)
        print(f"AY {year}-{str(year+1)[2:]} R{rnd}: {len(rows):>6} rows, {len(flags):>4} flagged")
        all_rows.extend(rows)
        all_flags.extend(flags)

    if args.discover:
        print("\nCategory-token census (freeze into constants.DSE_CATEGORY_LEGEND):")
        for tok, n in sorted(census.items()):
            print(f"  {tok:<12} {n}")
        return

    os.makedirs(os.path.dirname(OUT_ROWS), exist_ok=True)
    with open(OUT_ROWS, "w", encoding="utf-8") as f:
        json.dump(all_rows, f)
    with open(OUT_FLAGS, "w", encoding="utf-8") as f:
        json.dump(all_flags, f, indent=1)
    print(f"\nTotal: {len(all_rows)} validated rows -> {os.path.relpath(OUT_ROWS, ROOT)}")
    print(f"       {len(all_flags)} flagged     -> {os.path.relpath(OUT_FLAGS, ROOT)}")


if __name__ == "__main__":
    main()
