"""
fee_calculator.py  (Phase 4 — Priority 4, built ahead of order: preference_engine needs it)

Compute a student's ESTIMATED annual fee at a college for their category, using
the Maharashtra FRA structure. Fail-explicit: when a college has no tuition data
(93% of private colleges today) it returns available=False with reason — it NEVER
returns ₹0 or a guessed number that could silently pass a budget filter.

FRA structure (per design notes):
  Open                : tuition + development + fixed
  OBC / SEBC / EWS    : tuition/2 + development + fixed   (50% tuition concession)
  SC / ST / VJ / NT   : development + fixed               (tuition waived/reimbursed*)
  TFWS                : development + fixed               (full tuition waiver)
* SC/ST/VJ/NT waiver is income-linked reimbursement; out-of-pocket baseline shown.

compute_fee(conn, college_code, base_category) -> dict.
"""

import sqlite3

DB_PATH = "db/edupath.db"

# Fixed statutory charges (enrolment ₹200 + exam/other ₹2,626) — applies to all.
FIXED_FEES = 2826

# base_category prefix -> tuition multiplier + label
OPEN_CATS   = {"GOPEN", "LOPEN", "DEFOPEN", "PWDOPEN"}
HALF_CATS   = {"GOBC", "LOBC", "GSEBC", "LSEBC", "EWS", "PWDOBC", "PWDSEBC"}
WAIVE_CATS  = {"GSC", "LSC", "GST", "LST", "GVJ", "LVJ",
               "GNT1", "GNT2", "GNT3", "LNT1", "LNT2", "LNT3",
               "TFWS", "ORPHAN", "PWDSC"}


def _fee_class(base_category):
    """Return (tuition_multiplier, label) for a base category, or (None, None) if unknown."""
    b = base_category.upper()
    if b in OPEN_CATS:
        return 1.0, "full tuition"
    if b in HALF_CATS:
        return 0.5, "50% tuition concession"
    if b in WAIVE_CATS:
        return 0.0, "tuition waived (scheme/reimbursement)"
    return None, None


def compute_fee(conn, college_code, base_category):
    """
    Returns:
      { available: bool, college_code, base_category, fee_class,
        tuition_component, development, fixed, total_annual,
        source, reason }
    available=False when tuition data is missing OR category unknown.
    """
    mult, label = _fee_class(base_category)
    if mult is None:
        return {"available": False, "college_code": college_code,
                "base_category": base_category, "reason": "unknown category"}

    row = conn.execute("""
        SELECT fee_tuition_open, fee_development, fee_source
        FROM college_details WHERE college_code = ?
    """, (college_code,)).fetchone()

    if not row or row[0] is None:
        return {"available": False, "college_code": college_code,
                "base_category": base_category, "fee_class": label,
                "reason": "fee data unavailable for this college"}

    tuition_open, development, source = row
    development = development or 0
    tuition_component = round(tuition_open * mult)
    total = tuition_component + development + FIXED_FEES

    return {
        "available": True,
        "college_code": college_code,
        "base_category": base_category,
        "fee_class": label,
        "tuition_component": tuition_component,
        "development": development,
        "fixed": FIXED_FEES,
        "total_annual": total,
        "source": source or "unknown",
        "reason": None,
    }


if __name__ == "__main__":
    conn = sqlite3.connect(DB_PATH)
    # Smoke test against a real govt college (has DTE_standard fee data).
    code = conn.execute(
        "SELECT college_code FROM college_details WHERE fee_tuition_open IS NOT NULL LIMIT 1"
    ).fetchone()[0]
    for cat in ["GOPEN", "GOBC", "GSC", "TFWS", "ZZZ"]:
        print(cat, "->", compute_fee(conn, code, cat))
    # And a college without fee data
    nocode = conn.execute(
        "SELECT college_code FROM college_details WHERE fee_tuition_open IS NULL AND LENGTH(college_code)=5 LIMIT 1"
    ).fetchone()[0]
    print("no-fee college:", compute_fee(conn, nocode, "GOPEN"))
    conn.close()
