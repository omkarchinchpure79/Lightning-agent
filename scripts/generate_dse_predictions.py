"""
generate_dse_predictions.py — Build 2026 DSE cutoff predictions from dse_cutoffs.

Same model discipline as generate_predictions.py (FE):
  - predicted_pct = LATEST year's closing (carry-forward). The FE backtest on
    27,772 groups showed trend extrapolation is 44% worse; the same rule is
    applied here and must not be replaced without a DSE backtest proving a win.
  - closing per (branch, category, round, year) = MIN(merit_pct) across stages
    (the final allotment stage closes lowest).
  - calibrated predicted_low/predicted_high intervals via the SAME empirical
    method (constants.interval_offsets_from_groups), fit on DSE data itself.
  - groups whose newest data is older than 2024 are skipped (stale/dead codes).
  - rounds: 1-2 only (constants.DSE_VALID_ROUNDS) — rounds beyond II were last
    published in 2023 and would be presented as fresher than they are.

Confidence: 3 data years = high, 2 = medium, 1 = low; a volatile history
(spread > VOLATILITY_SPREAD_MAX) is capped at low, same as FE.
"""
import os
import sqlite3
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from constants import (  # noqa: E402
    DSE_VALID_ROUNDS, VOLATILITY_SPREAD_MAX, canonical_branch_key,
    ensure_dse_tables, interval_offsets_from_groups, tier_of_pct,
)

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(ROOT, "db", "edupath.db")

MIN_LATEST_DATA_YEAR = 2024  # same dead-code rule as FE


def main() -> int:
    conn = sqlite3.connect(DB_PATH)
    try:
        ensure_dse_tables(conn)
        placeholders = ",".join("?" * len(DSE_VALID_ROUNDS))
        rows = conn.execute(f"""
            SELECT college_code, college_name, choice_code, course_name,
                   category, round, year, MIN(merit_pct)
            FROM dse_cutoffs
            WHERE round IN ({placeholders})
            GROUP BY choice_code, category, round, year
        """, list(DSE_VALID_ROUNDS)).fetchall()
        print(f"{len(rows)} closing-cutoff rows fetched from dse_cutoffs.")

        groups = {}
        meta = {}
        for ccode, cname, choice, course, cat, rnd, yr, pct in rows:
            canon = canonical_branch_key(cname, course, choice)
            key = (canon, cat, rnd)
            g = groups.setdefault(key, {})
            if yr not in g or pct < g[yr]:
                g[yr] = pct
            # Keep the NEWEST year's identity fields for display.
            if key not in meta or yr >= meta[key][0]:
                meta[key] = (yr, ccode, cname, choice, course)
        print(f"{len(groups)} unique (branch, category, round) groups.")

        offsets = interval_offsets_from_groups(groups)
        print(f"Interval offsets fitted on DSE data: {len(offsets)} cells.")

        now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
        inserts, skipped_dead = [], 0
        conf_counts = {"high": 0, "medium": 0, "low": 0}
        for (canon, cat, rnd), g in groups.items():
            years = sorted(g)
            if years[-1] < MIN_LATEST_DATA_YEAR:
                skipped_dead += 1
                continue
            predicted = g[years[-1]]
            vals = [g[y] for y in years]
            spread = (max(vals) - min(vals)) if len(vals) > 1 else 0.0
            volatile = spread > VOLATILITY_SPREAD_MAX
            conf = {3: "high", 2: "medium"}.get(len(years), "low")
            if volatile:
                conf = "low"
            conf_counts[conf] += 1

            slope = None
            if len(years) >= 2:
                slope = round((g[years[-1]] - g[years[0]]) / (years[-1] - years[0]), 2)

            cell = offsets.get((tier_of_pct(predicted),
                                "volatile" if volatile else "stable"))
            low = high = None
            if cell:
                p10, _, p90 = cell
                low = round(max(0.0, min(100.0, predicted + p10)), 2)
                high = round(max(0.0, min(100.0, predicted + p90)), 2)

            _, ccode, cname, choice, course = meta[(canon, cat, rnd)]
            inserts.append((canon, ccode, cname, course, choice, cat, rnd,
                            predicted, low, high, slope, conf, len(years), now))

        conn.execute("DELETE FROM dse_predictions")
        conn.executemany(
            "INSERT INTO dse_predictions (canonical_code, college_code, college_name, "
            "branch_name, branch_code, category, round, predicted_pct, predicted_low, "
            "predicted_high, trend_slope, confidence, years_used, generated_at) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)", inserts)
        conn.commit()
    finally:
        conn.close()

    print(f"Skipped {skipped_dead} groups whose newest data predates {MIN_LATEST_DATA_YEAR}.")
    print(f"Generated {len(inserts)} DSE predictions "
          f"(high: {conf_counts['high']}, medium: {conf_counts['medium']}, low: {conf_counts['low']}).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
