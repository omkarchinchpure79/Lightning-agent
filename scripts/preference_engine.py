"""
preference_engine.py  (Phase 4 — Priority 1, the core deliverable)

Given a real student, produce a ranked SAFE / PROBABLE / REACH preference list of
college x branch options that the student is ACTUALLY eligible for, with the
correct Home/Other/State seat type resolved per college, a 2026 predicted close,
a fee estimate for the student's category, and a confidence level.

This is the piece predict.py never had: per-college seat eligibility. A `GOPENH`
seat is only "Home" for that college's university jurisdiction; for everyone else
it is `GOPENO`. The engine resolves that for every college before classifying.

Public API (Phase 5 frontend consumes the dict):
    compute_preference_list(percentile, base_category, home_district,
                            branch_preferences=None, fee_budget=None,
                            round_num=1, top_per_band=None) -> dict

Fail-explicit everywhere: unknown district / category / missing fee never crash
and never silently drop or pass a college — they surface as flags in the output.
"""

import sqlite3
import argparse
import sys

from constants import (
    normalize_district, resolve_seat_category, BASE_CATEGORY_VARIANTS,
    BAND_SAFE_MIN, BAND_PROBABLE_MIN, BAND_REACH_MIN,
)
from fee_calculator import compute_fee

DB_PATH = "db/edupath.db"
VALID_ROUNDS = (1, 2, 3, 4)


def resolve_student_university(conn, home_district):
    """
    home_district (raw) -> (university_code, university_name, canonical_district).
    Returns (None, None, None) if it can't be resolved — caller flags it; the
    student is then treated as Other everywhere (conservative: never grants a
    Home seat we can't justify).
    """
    canon = normalize_district(home_district)
    if not canon:
        return None, None, None
    row = conn.execute(
        "SELECT university_code, university_name FROM home_university_map WHERE district = ?",
        (canon,)
    ).fetchone()
    if not row:
        return None, None, canon
    return row[0], row[1], canon


def _band(student_pct, predicted, low, high, confidence):
    """
    Classify a student against a branch's CALIBRATED interval (predicted_low/
    predicted_high — the empirical P10/P90 error band fit by
    constants.compute_interval_offsets; see B2 in the improvement roadmap).

    Tier/volatility-scaled, replacing the old fixed +-3/-1/-4 margin thresholds:
      SAFE     - student_pct >= predicted_high (clears the cutoff even in the
                 tier's worst-case upward movement) AND confidence != low.
      PROBABLE - predicted_low <= student_pct < predicted_high, OR a would-be-SAFE
                 call downgraded because confidence is low (a shaky single-year
                 trend is never sold as a sure thing).
      REACH    - just below predicted_low, within a window scaled to how far
                 predicted_low itself sits below the point estimate (wide for
                 volatile/low-tier branches, tight for stable/elite ones).
      excluded - below the REACH floor -> returns None, caller drops the row.

    Falls back to the legacy fixed BAND_* thresholds on margin = student_pct -
    predicted if no interval is available (should not happen once
    generate_predictions.py has been run, but keeps the function total).
    """
    if low is None or high is None:
        margin = student_pct - predicted
        if margin >= BAND_SAFE_MIN:
            return "PROBABLE" if confidence == "low" else "SAFE"
        if margin >= BAND_PROBABLE_MIN:
            return "PROBABLE"
        if margin >= BAND_REACH_MIN:
            return "REACH"
        return None

    if student_pct >= high:
        return "PROBABLE" if confidence == "low" else "SAFE"
    if student_pct >= low:
        return "PROBABLE"
    reach_floor = low - max(predicted - low, 0.5)
    if student_pct >= reach_floor:
        return "REACH"
    return None


def _seat_label(matched_cat, variants):
    """Map the matched CAP code back to a human seat type using the variant tuple."""
    home_v, other_v, state_v = variants
    if matched_cat == home_v:
        return "Home"
    if matched_cat == other_v:
        return "Other"
    return "State"


def _location_match(haystack, needles):
    """Case-insensitive, either-direction substring match.

    'Pune' matches 'PUNE'; 'Mumbai' matches 'Mumbai City'/'MUMBAI SUBURBAN'.
    """
    if not haystack:
        return False
    h = haystack.lower()
    return any(n and (n.lower() in h or h in n.lower()) for n in needles)


def compute_preference_list(percentile, base_category, home_district,
                            branch_preferences=None, fee_budget=None,
                            round_num=1, top_per_band=None,
                            preferred_locations=None):
    if round_num not in VALID_ROUNDS:
        raise ValueError(f"round_num must be one of {VALID_ROUNDS}")
    if not 0.0 <= percentile <= 100.0:
        raise ValueError("percentile must be between 0 and 100")

    base_category = base_category.upper()
    variants = BASE_CATEGORY_VARIANTS.get(base_category)
    if not variants:
        return {"error": f"Unknown base category '{base_category}'. "
                         f"Use one of: {', '.join(sorted(BASE_CATEGORY_VARIANTS))}"}

    candidate_cats = [c for c in variants if c]  # H/O/S codes that exist for this base

    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA journal_mode=WAL")
    try:
        student_univ, student_univ_name, canon_district = \
            resolve_student_university(conn, home_district)

        placeholders = ",".join("?" * len(candidate_cats))
        rows = conn.execute(f"""
            SELECT p.canonical_code, p.college_code, p.college_name, p.branch_name,
                   p.category, p.predicted_pct, p.predicted_low, p.predicted_high,
                   p.confidence, p.trend_slope,
                   p.years_used, cd.university_code, col.city, col.score, cd.district,
                   p.branch_code, bi.general_intake, bi.tfws_intake, cd.affiliated_university
            FROM predictions_2026 p
            JOIN college_details cd ON cd.college_code = p.college_code
            LEFT JOIN colleges col  ON col.college_code = p.college_code
            LEFT JOIN branch_intake bi ON bi.canonical_code = p.canonical_code
            WHERE p.round = ? AND p.category IN ({placeholders})
        """, [round_num] + candidate_cats).fetchall()

        # Group by physical branch; keep every category variant available for it.
        branches = {}
        for (canon, ccode, cname, bname, cat, pred, pred_low, pred_high, conf, slope,
             yrs, univ, city, score, district, bcode, gen_intake, tfws_intake,
             affiliated_university) in rows:
            g = branches.setdefault(canon, {
                "college_code": ccode, "college_name": cname, "branch_name": bname,
                "college_univ": univ, "city": city, "score": score,
                "district": district, "branch_code": bcode,
                "general_intake": gen_intake, "tfws_intake": tfws_intake, "cats": {},
                "affiliated_university": affiliated_university,
            })
            # Prefer a non-null representative branch_code across category variants.
            if g["branch_code"] is None and bcode is not None:
                g["branch_code"] = bcode
            g["cats"][cat] = {"predicted_pct": pred, "predicted_low": pred_low,
                              "predicted_high": pred_high, "confidence": conf,
                              "slope": slope, "years_used": yrs}

        results = []
        for canon, g in branches.items():
            # Resolve which seat category THIS student uses at THIS college.
            chain = resolve_seat_category(base_category, student_univ, g["college_univ"])
            matched_cat = next((c for c in chain if c in g["cats"]), None)
            if matched_cat is None:
                continue  # no eligible seat predicted for this student here

            pinfo = g["cats"][matched_cat]
            predicted = pinfo["predicted_pct"]
            margin = round(percentile - predicted, 2)
            band = _band(percentile, predicted, pinfo["predicted_low"],
                         pinfo["predicted_high"], pinfo["confidence"])
            if band is None:
                continue

            fee = compute_fee(conn, g["college_code"], base_category)
            within_budget = None
            if fee_budget is not None:
                within_budget = fee["total_annual"] <= fee_budget if fee["available"] else None

            results.append({
                "canonical_code": canon,
                "college_code":   g["college_code"],
                "college_name":   g["college_name"],
                "branch_name":    g["branch_name"],
                "branch_code":    g["branch_code"],
                "affiliated_university": g["affiliated_university"],
                "general_intake": g["general_intake"],
                "tfws_intake":    g["tfws_intake"],
                "city":           g["city"] or "",
                "district":       g["district"] or "",
                "college_score":  g["score"],
                "seat_type":      _seat_label(matched_cat, variants),
                "category_used":  matched_cat,
                "predicted_close": predicted,
                "predicted_low":  pinfo["predicted_low"],
                "predicted_high": pinfo["predicted_high"],
                "margin":         margin,
                "band":           band,
                "confidence":     pinfo["confidence"],
                "trend_slope":    pinfo["slope"],
                "years_used":     pinfo["years_used"],
                "fee":            fee,
                "within_budget":  within_budget,
            })
    finally:
        conn.close()

    # Branch preference filter (substring match against any preferred keyword).
    if branch_preferences:
        keys = [k.lower() for k in branch_preferences]
        results = [r for r in results
                   if any(k in r["branch_name"].lower() for k in keys)]

    # Location preference filter — keep only colleges in the student's preferred
    # cities. The picker offers major CITY names, so match on city; fall back to
    # district only when city is missing. (Matching district unconditionally
    # leaks mislabeled rows, e.g. city='Nashik' district='Pune', into a Pune
    # filter.) Unlike home_district (which only drives Home/Other seat
    # eligibility), this actually restricts WHICH colleges appear.
    location_hidden = 0
    if preferred_locations:
        before = len(results)
        results = [
            r for r in results
            if _location_match(r["city"], preferred_locations)
            or (not r["city"] and _location_match(r["district"], preferred_locations))
        ]
        location_hidden = before - len(results)

    # Budget filter: never silently drop. Partition into in/over/unknown buckets.
    over_budget = unknown_fee = 0
    if fee_budget is not None:
        kept = []
        for r in results:
            if r["within_budget"] is True:
                kept.append(r)
            elif r["within_budget"] is False:
                over_budget += 1
            else:  # fee unknown -> keep but flag clearly
                unknown_fee += 1
                kept.append(r)
        results = kept

    # Sort within each band by DESIRABILITY, not margin. The best option in a band
    # is the most SELECTIVE one the student can still get there, so primary key is
    # the predicted cutoff (higher = more competitive/reputable), tie-broken by the
    # college quality score. Sorting by margin would surface the WORST colleges
    # first (biggest margin = lowest cutoff = sparse-data junk); sorting by score
    # alone lets one high-score college monopolize a band with all its branches.
    def sort_key(r):
        return (-r["predicted_close"], -(r["college_score"] or 0))

    bands = {"SAFE": [], "PROBABLE": [], "REACH": []}
    for r in results:
        bands[r["band"]].append(r)
    # counts reflect ALL eligible options; top_per_band only truncates display.
    full_counts = {b: len(bands[b]) for b in bands}
    for b in bands:
        bands[b].sort(key=sort_key)
        if top_per_band:
            bands[b] = bands[b][:top_per_band]

    return {
        "percentile": percentile,
        "base_category": base_category,
        "home_district": home_district,
        "resolved_district": canon_district,
        "student_university": student_univ,
        "student_university_name": student_univ_name,
        "round_num": round_num,
        "branch_preferences": branch_preferences,
        "preferred_locations": preferred_locations,
        "fee_budget": fee_budget,
        "counts": {"safe": full_counts["SAFE"], "probable": full_counts["PROBABLE"],
                   "reach": full_counts["REACH"],
                   "over_budget_hidden": over_budget, "fee_unknown_kept": unknown_fee,
                   "location_hidden": location_hidden},
        "district_unresolved": student_univ is None,
        "safe": bands["SAFE"], "probable": bands["PROBABLE"], "reach": bands["REACH"],
    }


def print_preference_list(data):
    if "error" in data:
        print(f"\nERROR: {data['error']}")
        return
    print(f"\n{'='*100}")
    print(f"  Preference List  |  {data['percentile']}%  |  {data['base_category']}  |  "
          f"Home district: {data['home_district']} -> "
          f"{data['student_university'] or 'UNRESOLVED'}  |  CAP Round {data['round_num']}")
    if data["district_unresolved"]:
        print("  WARNING: home district unresolved -> treated as OTHER university everywhere "
              "(no Home seats granted).")
    if data["branch_preferences"]:
        print(f"  Branch filter: {', '.join(data['branch_preferences'])}")
    if data["fee_budget"] is not None:
        print(f"  Fee budget: <= Rs {data['fee_budget']:,}/yr   "
              f"(over-budget hidden: {data['counts']['over_budget_hidden']}, "
              f"fee-unknown kept & flagged: {data['counts']['fee_unknown_kept']})")
    c = data["counts"]
    print(f"  SAFE: {c['safe']}   PROBABLE: {c['probable']}   REACH: {c['reach']}")
    print(f"{'='*100}")

    for band in ("SAFE", "PROBABLE", "REACH"):
        rows = data[band.lower()]
        if not rows:
            continue
        print(f"\n  -- {band} ({len(rows)}) " + "-"*40)
        print(f"  {'Branch':<38} {'College':<30} {'Seat':<6} {'Pred':>6} "
              f"{'Marg':>6} {'Conf':<7} {'Fee/yr':>10}")
        print("  " + "-"*104)
        for r in rows:
            fee = r["fee"]
            fee_str = f"Rs{fee['total_annual']:,}" if fee["available"] else "n/a"
            conf = r["confidence"] + ("" if fee["available"] else "*")
            print(f"  {r['branch_name'][:36]:<38} {r['college_name'][:28]:<30} "
                  f"{r['seat_type']:<6} {r['predicted_close']:>6.2f} "
                  f"{r['margin']:>+6.2f} {conf:<7} {fee_str:>10}")
    print()


def main():
    p = argparse.ArgumentParser(description="EduPath Phase 4 — counsellor preference list generator.")
    p.add_argument("--percentile", type=float, required=True)
    p.add_argument("--category", type=str, required=True,
                   help="BASE category: GOPEN, GSC, GOBC, GVJ, GNT1, LOPEN, EWS, TFWS ...")
    p.add_argument("--district", type=str, required=True, help="Student's home district")
    p.add_argument("--branch", type=str, action="append", default=None,
                   help="Preferred branch keyword (repeatable)")
    p.add_argument("--budget", type=int, default=None, help="Max annual fee in Rs")
    p.add_argument("--round", type=int, default=1, dest="round_num")
    p.add_argument("--top", type=int, default=15, help="Max results per band")
    args = p.parse_args()

    data = compute_preference_list(
        percentile=args.percentile, base_category=args.category,
        home_district=args.district, branch_preferences=args.branch,
        fee_budget=args.budget, round_num=args.round_num, top_per_band=args.top,
    )
    print_preference_list(data)


if __name__ == "__main__":
    main()
