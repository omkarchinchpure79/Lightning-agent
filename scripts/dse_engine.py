"""
dse_engine.py — SAFE / PROBABLE / REACH preference list for a DSE
(Direct Second Year / diploma lateral entry) student.

The DSE twin of preference_engine.compute_preference_list, with the parts
that do not exist in DSE removed rather than simulated:
  - NO Home/Other/State seat-type resolution (DSE cutoff categories carry no
    H/O/S suffix — the whole home-university layer is bypassed).
  - NO TFWS or reserved-pool merging (no TFWS quota in DSE; PWD/DEF/ORPHAN
    exist as plain categories a counsellor can select directly).
  - merit is the student's DIPLOMA AGGREGATE PERCENTAGE, matched against
    dse_predictions (built from diploma-percentage cutoffs). Same 0-100
    range as a percentile, never comparable with FE numbers.

Band thresholds/intervals are the same calibrated logic as FE
(preference_engine._band), because the classification question — "how does
the student's mark sit against the predicted close and its error band" —
is identical; only the mark's meaning differs.

Output dict shape mirrors compute_preference_list so the API/frontend reuse
the same rendering path, plus "admission_type": "dse".
"""
import os
import sqlite3
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from constants import DSE_CATEGORY_MAP, DSE_VALID_ROUNDS  # noqa: E402
from fee_calculator import compute_fee  # noqa: E402
from preference_engine import _band, _location_match  # noqa: E402

DB_PATH = "db/edupath.db"


def compute_dse_preference_list(diploma_pct, base_category,
                                branch_preferences=None, fee_budget=None,
                                round_num=1, top_per_band=None,
                                preferred_locations=None):
    if round_num not in DSE_VALID_ROUNDS:
        return {"error": f"DSE cutoffs are published for CAP rounds "
                         f"{'-'.join(str(r) for r in DSE_VALID_ROUNDS)} only; "
                         f"round {round_num} has no official DSE data."}
    if not 0.0 <= diploma_pct <= 100.0:
        raise ValueError("diploma_pct must be between 0 and 100")

    base_category = base_category.upper()
    if base_category not in DSE_CATEGORY_MAP:
        return {"error": f"Unknown base category '{base_category}'. "
                         f"Use one of: {', '.join(sorted(DSE_CATEGORY_MAP))}"}
    dse_category = DSE_CATEGORY_MAP[base_category]
    if dse_category is None:
        return {"error": f"Category '{base_category}' has no seat quota in DSE "
                         f"(e.g. TFWS exists only in first-year CAP)."}

    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA journal_mode=WAL")
    try:
        rows = conn.execute("""
            SELECT p.canonical_code, p.college_code, p.college_name, p.branch_name,
                   p.branch_code, p.predicted_pct, p.predicted_low, p.predicted_high,
                   p.confidence, p.trend_slope, p.years_used,
                   col.city, col.score, cd.district
            FROM dse_predictions p
            LEFT JOIN colleges col        ON col.college_code = p.college_code
            LEFT JOIN college_details cd  ON cd.college_code = p.college_code
            WHERE p.round = ? AND p.category = ?
        """, (round_num, dse_category)).fetchall()

        results = []
        for (canon, ccode, cname, bname, bcode, pred, low, high,
             conf, slope, yrs, city, score, district) in rows:
            margin = round(diploma_pct - pred, 2)
            band = _band(diploma_pct, pred, low, high, conf)
            if band is None:
                continue

            fee = compute_fee(conn, ccode, base_category)
            within_budget = None
            if fee_budget is not None:
                within_budget = fee["total_annual"] <= fee_budget if fee["available"] else None

            results.append({
                "canonical_code": canon,
                "college_code":   ccode,
                "college_name":   cname,
                "branch_name":    bname,
                "branch_code":    bcode,
                "general_intake": None,   # no DSE seat-intake source yet (docs/dse_design.md)
                "tfws_intake":    None,
                "city":           city or "",
                "district":       district or "",
                "college_score":  score,
                "seat_type":      "DSE",
                "category_used":  dse_category,
                "predicted_close": pred,
                "predicted_low":  low,
                "predicted_high": high,
                "margin":         margin,
                "band":           band,
                "confidence":     conf,
                "trend_slope":    slope,
                "years_used":     yrs,
                "fee":            fee,
                "within_budget":  within_budget,
            })
    finally:
        conn.close()

    if branch_preferences:
        keys = [k.lower() for k in branch_preferences]
        results = [r for r in results
                   if any(k in r["branch_name"].lower() for k in keys)]

    location_hidden = 0
    if preferred_locations:
        before = len(results)
        results = [
            r for r in results
            if _location_match(r["city"], preferred_locations)
            or (not r["city"] and _location_match(r["district"], preferred_locations))
        ]
        location_hidden = before - len(results)

    over_budget = unknown_fee = 0
    if fee_budget is not None:
        kept = []
        for r in results:
            if r["within_budget"] is True:
                kept.append(r)
            elif r["within_budget"] is False:
                over_budget += 1
            else:
                unknown_fee += 1
                kept.append(r)
        results = kept

    def sort_key(r):
        return (-r["predicted_close"], -(r["college_score"] or 0))

    bands = {"SAFE": [], "PROBABLE": [], "REACH": []}
    for r in results:
        bands[r["band"]].append(r)
    full_counts = {b: len(bands[b]) for b in bands}
    for b in bands:
        bands[b].sort(key=sort_key)
        if top_per_band:
            bands[b] = bands[b][:top_per_band]

    return {
        "admission_type": "dse",
        "percentile": diploma_pct,      # merit mark; labelled "diploma %" by the UI
        "base_category": base_category,
        "home_district": None,          # no home-university layer in DSE
        "resolved_district": None,
        "student_university": None,
        "student_university_name": None,
        "round_num": round_num,
        "branch_preferences": branch_preferences,
        "preferred_locations": preferred_locations,
        "fee_budget": fee_budget,
        "counts": {"safe": full_counts["SAFE"], "probable": full_counts["PROBABLE"],
                   "reach": full_counts["REACH"],
                   "over_budget_hidden": over_budget, "fee_unknown_kept": unknown_fee,
                   "location_hidden": location_hidden},
        "district_unresolved": False,   # not applicable — never show the FE warning
        "safe": bands["SAFE"], "probable": bands["PROBABLE"], "reach": bands["REACH"],
    }
