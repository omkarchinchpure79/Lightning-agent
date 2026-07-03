"""
backtest_predictions.py

Empirical validation of the prediction model: fit on the earlier years,
predict the latest year, score against what actually happened. This is the
evidence behind generate_predictions.py using carry-forward instead of
linear-trend extrapolation (audit 2026-07-02).

Method: for every (canonical branch, category, round) with closings in all
three years, predict 2025 from 2023+2024 with each candidate model and
report MAE / median AE / bias. Candidates:
  - carry-forward: predict = 2024 closing            <- production model
  - linear extrapolation: 2024 + (2024 - 2023)
  - damped trend, d in {0.15, 0.3, 0.5}
  - recency-weighted mean

Also reports carry-forward error stratified by historical volatility, which
justifies VOLATILITY_SPREAD_MAX (the low-confidence gate).

Usage: python scripts/backtest_predictions.py
Rerun whenever a new year of data lands (train on all-but-latest, score on
latest) BEFORE trusting the production model for the following year.
"""

import sqlite3
import statistics
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from constants import canonical_branch_key, compute_interval_offsets, tier_of_pct, VOLATILITY_SPREAD_MAX

DB_PATH = "db/edupath.db"


def yearly_closings(conn):
    """(canonical, category, round) -> {year: closing_pct}, MH MHT-CET rows only."""
    rows = conn.execute("""
        SELECT col.college_name, b.branch_name, cu.branch_code, cu.category,
               cu.round, cu.year, MIN(cu.percentile)
        FROM cutoffs cu
        JOIN branches b   ON cu.branch_code = b.branch_code
        JOIN colleges col ON b.college_code = col.college_code
        WHERE cu.is_all_india = 0 AND cu.exam_type LIKE 'MHT-CET%'
        GROUP BY cu.branch_code, cu.category, cu.round, cu.year
    """).fetchall()
    groups = {}
    for cname, bname, bc, cat, rnd, yr, pct in rows:
        key = (canonical_branch_key(cname, bname, bc), cat, rnd)
        g = groups.setdefault(key, {})
        if yr not in g or pct < g[yr]:
            g[yr] = pct
    return groups


def report(label, pred_actual_pairs):
    errs = [p - a for p, a in pred_actual_pairs]
    aes = [abs(e) for e in errs]
    print(f"  {label:28} n={len(errs):6}  MAE={statistics.mean(aes):6.3f}  "
          f"medAE={statistics.median(aes):6.3f}  "
          f"bias={statistics.mean(errs):+6.3f}  "
          f"P90AE={statistics.quantiles(aes, n=10)[8]:6.2f}")
    return statistics.mean(aes)


def report_interval_calibration(conn_path=DB_PATH):
    """
    Checks that the B1 interval (predicted_low/predicted_high) actually brackets
    the held-out actual closing at roughly the rate implied by its P10/P90 fit
    (~90% coverage), per (tier, volatility) cell. Uses the SAME fit-on-train/
    score-on-latest split as constants.compute_interval_offsets, so a row that
    falls outside [low, high] here is a genuine miss on the held-out year, not
    a self-graded one.
    """
    conn = sqlite3.connect(conn_path)
    try:
        groups = yearly_closings(conn)
        offsets = compute_interval_offsets(conn)
    finally:
        conn.close()

    years = sorted({y for g in groups.values() for y in g})
    if len(years) < 2:
        print("  Not enough years to check calibration.")
        return
    train_years, test_year = years[:-1], years[-1]
    clamp = lambda x: max(0.0, min(100.0, x))

    cells = {}
    for g in groups.values():
        if test_year not in g:
            continue
        train_pairs = sorted((y, g[y]) for y in train_years if y in g)
        if not train_pairs:
            continue
        predicted = train_pairs[-1][1]
        vals = [p for _, p in train_pairs]
        spread = (max(vals) - min(vals)) if len(vals) > 1 else 0.0
        vol = "stable" if spread <= VOLATILITY_SPREAD_MAX else "volatile"
        tier = tier_of_pct(predicted)
        p10, _p50, p90 = offsets.get((tier, vol), (0.0, 0.0, 0.0))
        low, high = clamp(predicted + p10), clamp(predicted + p90)
        actual = g[test_year]

        c = cells.setdefault((tier, vol), {"n": 0, "below_low": 0, "above_high": 0})
        c["n"] += 1
        if actual < low:
            c["below_low"] += 1
        if actual > high:
            c["above_high"] += 1

    print(f"  {'tier':7} {'volatility':10} {'n':>7} {'%below_low':>11} {'%above_high':>12} {'%in_band':>9}")
    for (tier, vol), c in sorted(cells.items()):
        n = c["n"]
        below = 100 * c["below_low"] / n
        above = 100 * c["above_high"] / n
        within = 100 - below - above
        print(f"  {tier:7} {vol:10} {n:7} {below:10.1f}% {above:11.1f}% {within:8.1f}%")


def main():
    conn = sqlite3.connect(DB_PATH)
    groups = yearly_closings(conn)
    conn.close()

    years = sorted({y for g in groups.values() for y in g})
    train, test = years[:-1], years[-1]
    print(f"Backtest: fit on {train}, score against actual {test} closings.\n")

    triples = [tuple(g[y] for y in train) + (g[test],)
               for g in groups.values() if all(y in g for y in years)]
    if not triples:
        print("Not enough overlapping data to backtest.")
        return

    clamp = lambda x: max(0.0, min(100.0, x))

    print("Model comparison (lower MAE = better):")
    mae_carry = report("carry-forward (production)",
                       [(t[-2], t[-1]) for t in triples])
    for d in (0.15, 0.3, 0.5, 1.0):
        label = "linear extrapolation" if d == 1.0 else f"damped trend d={d}"
        report(label, [(clamp(t[-2] + d * (t[-2] - t[0])), t[-1]) for t in triples])
    report("recency-weighted mean 30/70",
           [(0.3 * t[0] + 0.7 * t[-2], t[-1]) for t in triples])

    print("\nCarry-forward error by historical volatility (spread of train years):")
    for lo, hi in ((0, 2), (2, 5), (5, 10), (10, 20), (20, 101)):
        seg = [(t[-2], t[-1]) for t in triples if lo <= abs(t[-2] - t[0]) < hi]
        if seg:
            report(f"spread {lo}-{hi}", seg)

    print("\nBand calibration (B2): does the fitted P10/P90 interval actually bracket\n"
          "the held-out actual close, per (tier, volatility) cell?")
    report_interval_calibration(conn_path=DB_PATH)

    best_alt = min(
        statistics.mean(abs(clamp(t[-2] + d * (t[-2] - t[0])) - t[-1])
                        for t in triples)
        for d in (0.15, 0.3, 0.5, 1.0))
    if mae_carry <= best_alt:
        print("\nOK: carry-forward remains the best-or-equal model on this data.")
    else:
        print("\nWARNING: a trend model now beats carry-forward — re-evaluate "
              "generate_predictions.py before the next admission cycle.")


if __name__ == "__main__":
    main()
