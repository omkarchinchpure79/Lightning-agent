"""
generate_predictions.py
Builds 2026 cutoff predictions from 2023-2025 closing data.

MODEL (validated by backtest, see scripts/backtest_predictions.py):
  predicted close = the MOST RECENT year's closing (carry-forward).

  Linear-trend extrapolation was backtested on 27,772 (branch, category,
  round) groups by fitting 2023+2024 and scoring against actual 2025:
      2-pt linear extrapolation  MAE 11.98   bias +3.78
      carry-forward (last year)  MAE  8.32   bias -0.50
  Carry-forward wins in EVERY stratum (elite >=97 cutoffs, mid, low, stable,
  volatile) and at every damping level d>0. Year-to-year cutoff movement is
  noise-dominated; following the trend doubles the noise. The least-squares
  slope is still computed and stored — as TREND metadata for display, never
  as an extrapolation.

For each (canonical branch, category, round):
  - Collects closing percentile per year (MIN percentile = last seat allotted)
  - predicted_pct = latest year's closing; trend_slope = LS slope (display)
  - predicted_low/predicted_high = calibrated P10/P90 interval around predicted_pct,
    fit empirically per (tier, volatility) cell by constants.compute_interval_offsets
    (same fit-earlier/score-latest method as the backtest). The point estimate is at
    its accuracy ceiling; the interval is the honest uncertainty statement around it.
  - Stores in predictions_2026 table

Confidence:
  high   = 3 years of data, history spread <= 10 pts
  medium = 2 years of data, history spread <= 10 pts
  low    = 1 year of data, OR volatile history (spread > 10 pts)
  Volatility gate is backtest-derived: carry-forward MAE is 3.5-8.2 when the
  historical spread is under 10 pts but 11.4-14.2 above it — such predictions
  must never be sold as SAFE (the band logic blocks SAFE for low confidence).

Run after setup_college_profiles.py and load_db.py.
Usage:
    python scripts/generate_predictions.py
    python scripts/generate_predictions.py --category GOPENS --round 1
"""

import sqlite3
import argparse
import os
from datetime import datetime

from constants import (
    CATEGORY_FALLBACKS, canonical_branch_key, ensure_predictions_table,
    VOLATILITY_SPREAD_MAX, tier_of_pct, compute_interval_offsets,
)

DB_PATH = "db/edupath.db"

# Groups whose data all predates this year are DEAD codes: CET Cell re-numbered
# colleges in 2024 (4->5 digit), so a canonical key last seen in 2023 cannot be
# chosen in the 2026 CAP. Re-coded colleges already carry live predictions
# under their new code; predicting for the dead code would show students
# options that no longer exist. (14,301 such groups existed when added.)
MIN_LATEST_DATA_YEAR = 2024


def linear_predict(year_pct_pairs, target_year=2026):
    """
    Predict next year's closing for one branch from its yearly closings.
    `year_pct_pairs` MUST be sorted ascending by year.
    Returns (predicted_percentile, slope, years_used, reliable).

    predicted = the most recent year's closing (carry-forward — beats linear
    extrapolation by 44% MAE on the 2025 backtest; see module docstring).
    slope     = least-squares trend, kept ONLY as display metadata.
    reliable  = False when the history is too volatile (spread > 10 pts) for
    the prediction to be trusted; the caller downgrades confidence to low.
    target_year is accepted for interface stability but carry-forward does
    not extrapolate. Pure Python — no numpy needed.
    """
    n = len(year_pct_pairs)
    if n == 0:
        return None, None, 0, False

    ys = [p[1] for p in year_pct_pairs]
    recent = year_pct_pairs[-1][1]   # most recent year's closing (pairs sorted ascending)

    if n == 1:
        # Only one data point — no trend or volatility evidence, return it as-is
        return round(recent, 4), 0.0, 1, True

    xs = [p[0] for p in year_pct_pairs]
    x_mean = sum(xs) / n
    y_mean = sum(ys) / n

    numerator   = sum((x - x_mean) * (y - y_mean) for x, y in zip(xs, ys))
    denominator = sum((x - x_mean) ** 2 for x in xs)
    slope = numerator / denominator if denominator else 0.0

    reliable = (max(ys) - min(ys)) <= VOLATILITY_SPREAD_MAX
    return round(recent, 4), round(slope, 4), n, reliable


def fetch_historical_closing(conn, category_filter=None, round_filter=None):
    """
    Fetch closing percentile grouped by (college_name, branch_name, category, round, year).
    MH rows only (is_all_india = 0).
    Returns list of dicts.
    """
    cur = conn.cursor()

    where_clauses = ["cu.is_all_india = 0"]
    params = []

    if category_filter:
        # Exact match only — generate_predictions stores one canonical row per category.
        # Fallback expansion belongs in predict.py (query time), not here (generation time).
        where_clauses.append("cu.category = ?")
        params.append(category_filter)

    if round_filter:
        where_clauses.append("cu.round = ?")
        params.append(round_filter)

    # Only MHT-CET seats. All JEE/NEET rows happen to be is_all_india=1 today, but
    # filter explicitly so a future data load can never blend non-comparable exams.
    where_clauses.append("cu.exam_type LIKE 'MHT-CET%'")

    where_sql = " AND ".join(where_clauses)

    # MIN per PHYSICAL branch (branch_code) per year. Cross-year merging happens in
    # Python via canonical_branch_key, so we must NOT pre-group by name here.
    cur.execute(f"""
        SELECT
            col.college_name,
            b.branch_name,
            col.college_code,
            cu.branch_code,
            cu.category,
            cu.round,
            cu.year,
            MIN(cu.percentile) AS closing_pct
        FROM cutoffs cu
        JOIN branches b   ON cu.branch_code  = b.branch_code
        JOIN colleges col ON b.college_code  = col.college_code
        WHERE {where_sql}
        GROUP BY cu.branch_code, cu.category, cu.round, cu.year
        ORDER BY cu.branch_code, cu.category, cu.round, cu.year
    """, params)

    rows = cur.fetchall()
    cols = ["college_name","branch_name","college_code","branch_code",
            "category","round","year","closing_pct"]
    return [dict(zip(cols, r)) for r in rows]


def group_by_key(rows):
    """
    Group rows by (canonical_branch_key, category, round) so the same physical
    branch is correlated across years even when its code/name changed.
    Display fields (names, codes) are taken from the most recent year.
    Percentile per year = MIN across any branch_codes mapping to the same canonical
    key (handles parser-duplicate rows that share a canonical key within one year).
    """
    groups = {}
    for r in rows:
        canon = canonical_branch_key(r["college_name"], r["branch_name"], r["branch_code"])
        key = (canon, r["category"], r["round"])
        g = groups.get(key)
        if g is None:
            g = {
                "canonical_code": canon,
                "college_name":   r["college_name"],
                "branch_name":    r["branch_name"],
                "college_code":   r["college_code"],
                "branch_code":    r["branch_code"],
                "max_year":       r["year"],
                "year_pct":       {},
            }
            groups[key] = g

        yr, pct = r["year"], r["closing_pct"]
        if yr not in g["year_pct"] or pct < g["year_pct"][yr]:
            g["year_pct"][yr] = pct

        if yr >= g["max_year"]:
            g["max_year"]     = yr
            g["college_name"] = r["college_name"]
            g["branch_name"]  = r["branch_name"]
            g["branch_code"]  = r["branch_code"]
            g["college_code"] = r["college_code"]
    return groups


def generate(conn, category_filter=None, round_filter=None):
    print("Fetching historical closing cutoffs...")
    rows = fetch_historical_closing(conn, category_filter, round_filter)
    print(f"  {len(rows)} closing cutoff rows fetched.")

    groups = group_by_key(rows)
    print(f"  {len(groups)} unique (college, branch, category, round) groups.")

    print("Fitting calibrated interval offsets (tier x volatility, backtest-derived)...")
    offsets = compute_interval_offsets(conn)
    clamp = lambda x: max(0.0, min(100.0, x))

    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    records = []

    stale = 0
    for (canon, category, round_num), data in groups.items():
        if data["max_year"] < MIN_LATEST_DATA_YEAR:
            stale += 1   # dead code — not selectable in the next CAP
            continue

        year_pct = sorted(data["year_pct"].items())
        predicted, slope, n_years, reliable = linear_predict(year_pct, target_year=2026)

        if predicted is None:
            continue

        # Confidence = how many years of data we have, but a volatile history
        # (yearly closings spread > VOLATILITY_SPREAD_MAX, typical of sparse
        # single-seat reserved categories) is always "low" no matter the year
        # count — backtest shows such carry-forwards err by 11-14 pts MAE and
        # must never be classified SAFE.
        if not reliable:
            confidence = "low"
        elif n_years >= 3:
            confidence = "high"
        elif n_years == 2:
            confidence = "medium"
        else:
            confidence = "low"

        # Calibrated interval (Phase 5 roadmap B1): empirical P10/P90 error offset
        # for this row's (tier, volatility) cell, applied to the point estimate.
        # Falls back to a symmetric zero-width interval if no offsets were fit
        # (e.g. fewer than 2 years of history in the whole DB).
        vol = "stable" if reliable else "volatile"
        p10, _p50, p90 = offsets.get((tier_of_pct(predicted), vol), (0.0, 0.0, 0.0))
        predicted_low = round(clamp(predicted + p10), 4)
        predicted_high = round(clamp(predicted + p90), 4)

        records.append((
            data["canonical_code"],
            data["college_name"],
            data["branch_name"],
            data["college_code"],
            data["branch_code"],
            category,
            round_num,
            predicted,
            predicted_low,
            predicted_high,
            slope,
            confidence,
            n_years,
            now_str,
        ))

    if stale:
        print(f"  Skipped {stale} groups whose code last appeared before "
              f"{MIN_LATEST_DATA_YEAR} (dead codes, not selectable in 2026 CAP).")
    print(f"  Generated {len(records)} predictions. Inserting...")

    cur = conn.cursor()

    # Clear existing predictions for the filtered scope
    if category_filter and round_filter:
        cur.execute("DELETE FROM predictions_2026 WHERE category=? AND round=?",
                    (category_filter, round_filter))
    elif category_filter:
        cur.execute("DELETE FROM predictions_2026 WHERE category=?", (category_filter,))
    elif round_filter:
        cur.execute("DELETE FROM predictions_2026 WHERE round=?", (round_filter,))
    else:
        cur.execute("DELETE FROM predictions_2026")

    cur.executemany("""
        INSERT OR REPLACE INTO predictions_2026
            (canonical_code, college_name, branch_name, college_code, branch_code,
             category, round, predicted_pct, predicted_low, predicted_high,
             trend_slope, confidence, years_used, generated_at)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)
    """, records)

    conn.commit()

    # Summary  (confidence is index 11: canonical_code..predicted_high shifted every field)
    high   = sum(1 for r in records if r[11] == "high")
    medium = sum(1 for r in records if r[11] == "medium")
    low    = sum(1 for r in records if r[11] == "low")
    print(f"\n  Confidence breakdown:")
    print(f"    High   (3 years data): {high}")
    print(f"    Medium (2 years data): {medium}")
    print(f"    Low    (1 year  data): {low}")
    return len(records)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate 2026 cutoff predictions.")
    parser.add_argument("--category", type=str, default=None,
                        help="Only generate for this category (e.g. GOPENS). Default: all.")
    parser.add_argument("--round", type=int, default=None, dest="round_num",
                        help="Only generate for this round (1-4). Default: all.")
    args = parser.parse_args()

    if not os.path.exists(DB_PATH):
        print(f"ERROR: {DB_PATH} not found. Run load_db.py first.")
        exit(1)

    if args.round_num is not None and args.round_num not in (1, 2, 3, 4):
        print(f"ERROR: round must be 1-4, got {args.round_num}")
        exit(1)

    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA journal_mode=WAL")

    # Schema is owned by constants.ensure_predictions_table (single source of truth);
    # safe to run even if setup_college_profiles.py wasn't run first.
    if ensure_predictions_table(conn):
        print("  Dropped stale predictions_2026 (missing canonical_code) — recreating.")
    conn.commit()

    total = generate(conn, category_filter=args.category, round_filter=args.round_num)
    conn.close()
    print(f"\nDone. {total} predictions stored in predictions_2026.")
