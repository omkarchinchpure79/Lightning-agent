"""
EduPath Prediction Engine
Counsellor-facing tool: given a student's percentile + category, predict seat allotment
probability for all branches based on 3 years of historical CAP cutoff data.

compute_prediction() returns structured data — used by both CLI and Phase 5 web API.
print_prediction()  formats and prints to terminal.
run_prediction()    glue for CLI usage.

Usage:
    python scripts/predict.py --percentile 95.5 --category GOPENS
    python scripts/predict.py --percentile 88.0 --category GOPENH --round 1 --city Pune --branch "Computer"
    python scripts/predict.py --percentile 72.0 --category GSCS --top 20
    python scripts/predict.py --percentile 95.0 --category GOPENS --show-cutoffs
"""

import sqlite3
import argparse
import math
import sys

from constants import (
    CATEGORY_FALLBACKS, YEAR_WEIGHTS, canonical_branch_key,
    DSE_CATEGORY_LEGEND, DSE_VALID_ROUNDS,
)

DB_PATH = "db/edupath.db"
VALID_ROUNDS = (1, 2, 3, 4)


def get_predictions_2026(conn, category, round_num):
    """
    Fetch 2026 predicted cutoffs keyed by canonical_code (the same stable branch
    identity generate_predictions.py stores), so lookup and generation always agree.
    Exact category match takes priority over fallback category.
    """
    cur = conn.cursor()
    cats = [category] + CATEGORY_FALLBACKS.get(category, [])
    placeholders = ",".join("?" * len(cats))
    try:
        cur.execute(f"""
            SELECT canonical_code, predicted_pct, trend_slope, confidence, category
            FROM predictions_2026
            WHERE category IN ({placeholders}) AND round = ?
        """, cats + [round_num])
        rows = cur.fetchall()
        result = {}
        for canon, predicted_pct, slope, confidence, cat in rows:
            if canon not in result or cat == category:   # exact match overwrites fallback
                result[canon] = {
                    "predicted_pct": predicted_pct,
                    "slope":         slope,
                    "confidence":    confidence,
                }
        return result
    except sqlite3.OperationalError:
        return {}


def get_college_scores(conn):
    """Returns dict: college_code -> {score, completeness}."""
    cur = conn.cursor()
    cur.execute("SELECT college_code, score, completeness FROM colleges WHERE score IS NOT NULL")
    return {
        row[0]: {"score": row[1], "completeness": row[2]}
        for row in cur.fetchall()
    }


def get_closing_cutoffs(conn, category, round_num):
    """
    Return closing cutoffs as one row per (physical branch_code, year, category).

    CET Cell re-codes the same physical college/branch across years, so cross-year
    merging is done in Python via canonical_branch_key() — the SAME function
    generate_predictions.py uses — NOT by grouping on name here. This guarantees
    the prediction lookup and the prediction generation correlate identical branches.

    Filters mirror generate_predictions.fetch_historical_closing exactly
    (is_all_india = 0, exam_type LIKE 'MHT-CET%') so the historical basis matches.
    """
    cur = conn.cursor()
    cats = [category] + CATEGORY_FALLBACKS.get(category, [])
    placeholders = ",".join("?" * len(cats))

    cur.execute(f"""
        SELECT
            col.college_name,
            b.branch_name,
            col.college_code,
            cu.branch_code,
            col.city,
            cu.year,
            MIN(cu.percentile) AS closing_pct,
            cu.category
        FROM cutoffs cu
        JOIN branches b   ON cu.branch_code  = b.branch_code
        JOIN colleges col ON b.college_code  = col.college_code
        WHERE cu.category IN ({placeholders})
          AND cu.round = ?
          AND cu.is_all_india = 0
          AND cu.exam_type LIKE 'MHT-CET%'
        GROUP BY cu.branch_code, cu.year, cu.category
    """, cats + [round_num])

    return cur.fetchall()


def compute_probability(student_pct, cutoffs_by_year):
    """
    Given student percentile and {year: closing_pct}, return weighted probability 0-100.

    - margin = student_pct - closing_pct (positive = student above cutoff)
    - Sigmoid: k=0.25, margin +5 -> ~78%, 0 -> 50%, -5 -> ~22%
    - Weighted by year recency (YEAR_WEIGHTS)
    - Clamped to [7%, 93%] — never near-certainty in either direction

    k and the clamp are CALIBRATED against real outcomes (2023+2024 data
    scored on actual 2025 closings, 350k samples): the old k=0.4/0.98 clamp
    claimed 90-100% for seats that materialised only 80% of the time.
    With k=0.25/0.93 the top band (80-90%) matches its observed 80.0% rate.
    Cutoff movement has fat tails (P90 year-over-year move ~22 pts on
    volatile branches), so certainty above ~93% is never honest.
    """
    if not cutoffs_by_year:
        return None, {}

    total_weight   = 0.0
    weighted_score = 0.0
    details        = {}

    for year, closing_pct in sorted(cutoffs_by_year.items()):
        weight    = YEAR_WEIGHTS.get(year, 0.25)
        margin    = student_pct - closing_pct
        raw_score = 1.0 / (1.0 + math.exp(-0.25 * margin))
        score     = max(0.07, min(0.93, raw_score))

        weighted_score += weight * score
        total_weight   += weight
        details[year]   = {
            "closing_pct": round(closing_pct, 4),
            "margin":      round(margin, 4),
            "year_prob":   round(score * 100, 1),
        }

    probability = (weighted_score / total_weight) * 100 if total_weight > 0 else None
    return round(probability, 1) if probability is not None else None, details


def compute_prediction(percentile, category, round_num=1, city_filter=None, branch_filter=None, top_n=50):
    """
    Core prediction logic. Returns structured dict — usable by both CLI and web API.

    Return shape:
    {
        "percentile": float, "category": str, "round_num": int,
        "city_filter": str|None, "branch_filter": str|None,
        "top_n": int, "total_branches": int,
        "results": [
            {
                "rank": int, "branch_code": str, "branch_name": str,
                "college_code": str, "college_name": str, "city": str,
                "college_score": float|None, "completeness": float|None,
                "category_used": str, "probability": float,
                "cutoffs": {year: closing_pct}, "details": {...},
                "years_with_data": int,
                "pred_2026": float|None, "trend_slope": float|None,
                "pred_confidence": str,
            }, ...
        ]
    }
    """
    if round_num not in VALID_ROUNDS:
        raise ValueError(f"round_num must be one of {VALID_ROUNDS}, got {round_num}")

    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA journal_mode=WAL")
    try:
        predictions_2026 = get_predictions_2026(conn, category, round_num)
        college_scores   = get_college_scores(conn)
        rows             = get_closing_cutoffs(conn, category, round_num)
    finally:
        conn.close()

    # Group cutoff rows by canonical branch identity — the SAME key
    # generate_predictions.py uses — so a branch re-coded across years merges
    # into one entry and lines up with its 2026 prediction.
    branch_data = {}
    for college_name, branch_name, college_code, branch_code, city, year, closing_pct, matched_cat in rows:
        canon = canonical_branch_key(college_name, branch_name, branch_code)
        g = branch_data.get(canon)
        if g is None:
            g = {
                "branch_code":   branch_code,
                "college_code":  college_code,
                "college_name":  college_name,
                "branch_name":   branch_name,
                "city":          city,
                "cutoffs":       {},
                "year_cat":      {},   # year -> category code that set that year's cutoff
                "category_used": matched_cat,
                "max_year":      year,
            }
            branch_data[canon] = g

        # Per-year merge rule: an exact category match always beats a fallback
        # match; within the same tier, keep the MIN (most restrictive) percentile.
        is_exact     = (matched_cat == category)
        existing_pct = g["cutoffs"].get(year)
        if existing_pct is None:
            g["cutoffs"][year]  = closing_pct
            g["year_cat"][year] = matched_cat
        else:
            existing_exact = (g["year_cat"].get(year) == category)
            if is_exact and not existing_exact:
                g["cutoffs"][year]  = closing_pct          # exact replaces fallback
                g["year_cat"][year] = matched_cat
            elif is_exact == existing_exact and closing_pct < existing_pct:
                g["cutoffs"][year]  = closing_pct          # same tier -> take MIN
                g["year_cat"][year] = matched_cat
            # else: existing is exact and new is fallback -> keep existing

        # Display fields (name/code/city) taken from the most recent year of data.
        if year >= g["max_year"]:
            g["max_year"]      = year
            g["branch_code"]   = branch_code
            g["college_code"]  = college_code
            g["college_name"]  = college_name
            g["branch_name"]   = branch_name
            g["city"]          = city
            g["category_used"] = g["year_cat"].get(year, matched_cat)

    results = []
    for canon, data in branch_data.items():
        prob, details = compute_probability(percentile, data["cutoffs"])
        if prob is None:
            continue

        pred_info = predictions_2026.get(canon, {})
        y_data    = college_scores.get(data["college_code"], {})

        results.append({
            "branch_code":     data["branch_code"],
            "branch_name":     data["branch_name"],
            "college_code":    data["college_code"],
            "college_name":    data["college_name"],
            "city":            data["city"] or "",
            "college_score":   y_data.get("score"),
            "completeness":    y_data.get("completeness"),
            "category_used":   data["category_used"],
            "probability":     prob,
            "cutoffs":         data["cutoffs"],
            "details":         details,
            "years_with_data": len(data["cutoffs"]),
            "pred_2026":       pred_info.get("predicted_pct"),
            "trend_slope":     pred_info.get("slope"),
            "pred_confidence": pred_info.get("confidence", ""),
        })

    if city_filter:
        results = [r for r in results if city_filter.lower() in r["city"].lower()]
    if branch_filter:
        results = [r for r in results if branch_filter.lower() in r["branch_name"].lower()]

    results.sort(key=lambda r: (
        -r["probability"],
        -(r["college_score"] or 0),
        -(r["cutoffs"].get(2025) or r["cutoffs"].get(2024) or 0),
    ))

    total   = len(results)
    results = results[:top_n]
    for i, r in enumerate(results, 1):
        r["rank"] = i

    return {
        "percentile":     percentile,
        "category":       category,
        "round_num":      round_num,
        "city_filter":    city_filter,
        "branch_filter":  branch_filter,
        "top_n":          top_n,
        "total_branches": total,
        "results":        results,
    }


def get_dse_predictions(conn, category, round_num):
    """DSE twin of get_predictions_2026: exact category match only (no fallback
    families — DSE_CATEGORY_LEGEND categories don't have the FE tier-fallback
    concept)."""
    cur = conn.cursor()
    try:
        cur.execute("""
            SELECT canonical_code, predicted_pct, trend_slope, confidence
            FROM dse_predictions
            WHERE category = ? AND round = ?
        """, (category, round_num))
        return {
            canon: {"predicted_pct": pct, "slope": slope, "confidence": conf}
            for canon, pct, slope, conf in cur.fetchall()
        }
    except sqlite3.OperationalError:
        return {}


def get_dse_closing_cutoffs(conn, category, round_num):
    """
    DSE twin of get_closing_cutoffs. dse_cutoffs already carries college_code/
    college_name/course_name directly (no branches join needed, unlike FE).
    City comes from a LEFT JOIN against colleges (DSE college_code values are
    the same institute codes FE uses) -- absent for colleges without a
    `colleges` row, never guessed.
    """
    cur = conn.cursor()
    cur.execute("""
        SELECT dc.college_name, dc.course_name, dc.college_code, dc.choice_code,
               col.city, dc.year, MIN(dc.merit_pct)
        FROM dse_cutoffs dc
        LEFT JOIN colleges col ON col.college_code = dc.college_code
        WHERE dc.category = ? AND dc.round = ?
        GROUP BY dc.choice_code, dc.year
    """, (category, round_num))
    return cur.fetchall()


def compute_dse_prediction(diploma_pct, category, round_num=1, city_filter=None,
                            branch_filter=None, top_n=50):
    """
    DSE twin of compute_prediction(). Same probability model (compute_probability
    is generic over any 0-100 merit metric) reused as-is -- NOT independently
    calibrated against DSE outcomes (unlike the FE k=0.25/93% clamp, which was
    fit against actual 2025 allotments). Treat DSE probabilities as directional,
    not as precisely calibrated as the FE ones, until a DSE backtest is run.
    """
    if round_num not in DSE_VALID_ROUNDS:
        raise ValueError(f"round_num must be one of {DSE_VALID_ROUNDS}, got {round_num}")
    if category not in DSE_CATEGORY_LEGEND:
        raise ValueError(f"category must be a DSE category ({sorted(DSE_CATEGORY_LEGEND)}), got {category!r}")

    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA journal_mode=WAL")
    try:
        dse_predictions = get_dse_predictions(conn, category, round_num)
        college_scores  = get_college_scores(conn)
        rows            = get_dse_closing_cutoffs(conn, category, round_num)
    finally:
        conn.close()

    branch_data = {}
    for college_name, course_name, college_code, choice_code, city, year, closing_pct in rows:
        canon = canonical_branch_key(college_name, course_name, choice_code)
        g = branch_data.get(canon)
        if g is None:
            g = {
                "branch_code":  choice_code,
                "college_code": college_code,
                "college_name": college_name,
                "branch_name":  course_name,
                "city":         city,
                "cutoffs":      {},
                "max_year":     year,
            }
            branch_data[canon] = g

        existing_pct = g["cutoffs"].get(year)
        if existing_pct is None or closing_pct < existing_pct:
            g["cutoffs"][year] = closing_pct

        if year >= g["max_year"]:
            g["max_year"]     = year
            g["branch_code"]  = choice_code
            g["college_code"] = college_code
            g["college_name"] = college_name
            g["branch_name"]  = course_name
            g["city"]         = city

    results = []
    for canon, data in branch_data.items():
        prob, details = compute_probability(diploma_pct, data["cutoffs"])
        if prob is None:
            continue

        pred_info = dse_predictions.get(canon, {})
        y_data    = college_scores.get(data["college_code"], {})

        results.append({
            "branch_code":     data["branch_code"],
            "branch_name":     data["branch_name"],
            "college_code":    data["college_code"],
            "college_name":    data["college_name"],
            "city":            data["city"] or "",
            "college_score":   y_data.get("score"),
            "completeness":    y_data.get("completeness"),
            "category_used":   category,
            "probability":     prob,
            "cutoffs":         data["cutoffs"],
            "details":         details,
            "years_with_data": len(data["cutoffs"]),
            "pred_2026":       pred_info.get("predicted_pct"),
            "trend_slope":     pred_info.get("slope"),
            "pred_confidence": pred_info.get("confidence", ""),
        })

    if city_filter:
        results = [r for r in results if city_filter.lower() in r["city"].lower()]
    if branch_filter:
        results = [r for r in results if branch_filter.lower() in r["branch_name"].lower()]

    results.sort(key=lambda r: (
        -r["probability"],
        -(r["college_score"] or 0),
        -(r["cutoffs"].get(2025) or r["cutoffs"].get(2024) or 0),
    ))

    total   = len(results)
    results = results[:top_n]
    for i, r in enumerate(results, 1):
        r["rank"] = i

    return {
        "percentile":     diploma_pct,
        "category":       category,
        "round_num":      round_num,
        "city_filter":    city_filter,
        "branch_filter":  branch_filter,
        "top_n":          top_n,
        "total_branches": total,
        "results":        results,
        "admission_type": "dse",
    }


def print_prediction(data, show_cutoffs=False):
    """Format and print prediction results to terminal. Reads the dict from compute_prediction()."""
    percentile = data["percentile"]
    results    = data["results"]
    total      = data["total_branches"]
    top_n      = data["top_n"]

    is_dse = data.get("admission_type") == "dse"
    metric_label = "Diploma %" if is_dse else "Student Percentile"

    print(f"\n{'='*90}")
    print(f"  EduPath Prediction: CAP Round {data['round_num']} | Category: {data['category']} | {metric_label}: {percentile}%"
          + ("  [Direct Second Year]" if is_dse else ""))
    if data["city_filter"]:
        print(f"  City filter: {data['city_filter']}")
    if data["branch_filter"]:
        print(f"  Branch filter: {data['branch_filter']}")
    print(f"  Showing top {min(top_n, total)} of {total} branches with data")
    print(f"{'='*90}")

    if not results:
        print("  No branches found with historical data for this category/round combination.")
        return

    print(f"\n{'#':<4} {'Prob':<6} {'Branch':<42} {'College':<32} {'City':<10} {'2026 Pred':<11} {'Trend':<8} {'YScore'}")
    print("-" * 120)

    for r in results:
        prob_str      = f"{r['probability']:.0f}%"
        branch_short  = r["branch_name"][:40]
        college_short = r["college_name"][:30]
        city_str      = (r["city"] or "-")[:9]

        if r["pred_2026"] is not None:
            pred_str  = f"{r['pred_2026']:.2f}%"
            slope     = r["trend_slope"] or 0
            if slope > 0.3:
                trend_str = f"^{slope:+.2f}"
            elif slope < -0.3:
                trend_str = f"v{slope:+.2f}"
            else:
                trend_str = f"~{slope:+.2f}"
            conf_mark = {"high": "", "medium": "~", "low": "?"}.get(r["pred_confidence"], "")
            pred_str  = conf_mark + pred_str
        else:
            pred_str  = "-"
            trend_str = "-"

        y_score_str = f"{r['college_score']:.1f}" if r["college_score"] else "N/A"

        if r["probability"] >= 80:
            indicator = "+++"
        elif r["probability"] >= 60:
            indicator = "++"
        elif r["probability"] >= 40:
            indicator = "+ "
        elif r["probability"] >= 20:
            indicator = "~ "
        else:
            indicator = "- "

        print(f"{r['rank']:<4} {prob_str:<5} {indicator} {branch_short:<40} {college_short:<30} {city_str:<9} {pred_str:<11} {trend_str:<8} {y_score_str}")

        if show_cutoffs and r["cutoffs"]:
            parts = []
            for yr in sorted(r["cutoffs"].keys()):
                pct    = r["cutoffs"][yr]
                margin = percentile - pct
                sign   = "+" if margin >= 0 else ""
                parts.append(f"{yr}: {pct:.2f}% ({sign}{margin:.2f})")
            if r["pred_2026"] is not None:
                parts.append(f"2026(pred): {r['pred_2026']:.2f}%")
            print(f"     Cutoffs -> {' | '.join(parts)}")

    print()
    high = sum(1 for r in results if r["probability"] >= 70)
    mid  = sum(1 for r in results if 40 <= r["probability"] < 70)
    low  = sum(1 for r in results if r["probability"] < 40)
    print(f"  Summary (top {min(top_n, total)}): High (>=70%): {high}  |  Moderate (40-70%): {mid}  |  Low (<40%): {low}")
    print()


def run_prediction(percentile, category, round_num=1, city_filter=None, branch_filter=None,
                    top_n=50, show_cutoffs=False, admission_type="fe"):
    """CLI entry point: compute and print. admission_type='dse' routes to the
    Direct Second Year data plane (dse_cutoffs/dse_predictions) instead of FE's."""
    if admission_type == "dse":
        data = compute_dse_prediction(percentile, category, round_num, city_filter, branch_filter, top_n)
    else:
        data = compute_prediction(percentile, category, round_num, city_filter, branch_filter, top_n)
    print_prediction(data, show_cutoffs)


def main():
    parser = argparse.ArgumentParser(
        description="EduPath: Predict CAP seat allotment probability for a student.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python scripts/predict.py --percentile 95.5 --category GOPENS
  python scripts/predict.py --percentile 88.0 --category GOPENH --city Pune --branch "Computer"
  python scripts/predict.py --percentile 72.0 --category GSCS --top 20 --show-cutoffs
  python scripts/predict.py --percentile 95.0 --category GOPENS --round 2
  python scripts/predict.py --percentile 60.0 --category EWS --round 1
  python scripts/predict.py --admission-type dse --percentile 88.0 --category GOPEN
  python scripts/predict.py --admission-type dse --percentile 75.0 --category GNTB --round 2
        """
    )
    parser.add_argument("--percentile", type=float, required=True,
                        help="Student's MHT-CET percentile for FE, or diploma aggregate %% for DSE (0.0 to 100.0)")
    parser.add_argument("--category",   type=str,   required=True,
                        help="Seat category. FE: e.g. GOPENS, GOPENH, GSCS, EWS, TFWS. "
                             "DSE: e.g. GOPEN, GSC, GNTB, EWS (see constants.DSE_CATEGORY_LEGEND) -- no TFWS in DSE")
    parser.add_argument("--admission-type", type=str, default="fe", choices=["fe", "dse"],
                        dest="admission_type",
                        help="'fe' (first-year MHT-CET, default) or 'dse' (Direct Second Year diploma lateral entry)")
    parser.add_argument("--round",      type=int,   default=1, dest="round_num",
                        help="CAP round: FE 1-4, DSE 1-2 (default: 1)")
    parser.add_argument("--city",       type=str,   default=None,
                        help="Filter by city (partial match, e.g. Pune, Mumbai)")
    parser.add_argument("--branch",     type=str,   default=None,
                        help="Filter by branch keyword (e.g. Computer, Mechanical)")
    parser.add_argument("--top",        type=int,   default=50,
                        help="Number of results to show (default: 50)")
    parser.add_argument("--show-cutoffs", action="store_true",
                        help="Show year-wise historical cutoffs and margin per branch")

    args = parser.parse_args()

    if not 0.0 <= args.percentile <= 100.0:
        print(f"Error: percentile must be between 0 and 100, got {args.percentile}")
        sys.exit(1)

    valid_rounds = DSE_VALID_ROUNDS if args.admission_type == "dse" else VALID_ROUNDS
    if args.round_num not in valid_rounds:
        print(f"Error: round must be one of {valid_rounds} for admission-type={args.admission_type}, got {args.round_num}")
        sys.exit(1)

    category = args.category.upper()
    if args.admission_type == "dse" and category not in DSE_CATEGORY_LEGEND:
        print(f"Error: {category!r} is not a DSE category. Valid: {sorted(DSE_CATEGORY_LEGEND)}")
        sys.exit(1)

    run_prediction(
        percentile=args.percentile,
        category=category,
        round_num=args.round_num,
        city_filter=args.city,
        branch_filter=args.branch,
        top_n=args.top,
        show_cutoffs=args.show_cutoffs,
        admission_type=args.admission_type,
    )


if __name__ == "__main__":
    main()
