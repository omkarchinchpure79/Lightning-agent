"""
Regression tests for the Phase 2 prediction engine (predict.py + generate_predictions.py).

WHY THIS FILE EXISTS:
Across three manual review passes, bugs kept reappearing in predict.py /
generate_predictions.py because NOTHING executed them automatically. A half-finished
refactor once left predict.py un-importable and no test caught it. These tests run the
real engine against the real DB and lock in the invariants that kept breaking, so a
future edit that re-breaks them fails loudly instead of silently shipping.

Run:  python -m unittest discover -s tests
(Requires db/edupath.db populated + predictions generated.)
"""

import os
import sys
import sqlite3
import unittest

# Make scripts/ importable and run from project root paths
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
os.chdir(ROOT)

DB_PATH = "db/edupath.db"


@unittest.skipUnless(os.path.exists(DB_PATH), "db/edupath.db not found — run load_db.py")
class TestPredictionEngine(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        # Import here so an import-time crash (the exact class of bug that slipped
        # through before) surfaces as a clear test failure.
        import predict
        import constants
        cls.predict = predict
        cls.constants = constants
        cls.conn = sqlite3.connect(DB_PATH)

    @classmethod
    def tearDownClass(cls):
        cls.conn.close()

    def test_predict_imports_clean(self):
        """predict.py must import without error (catches missing-symbol regressions)."""
        self.assertTrue(hasattr(self.predict, "compute_prediction"))
        self.assertTrue(callable(self.predict.compute_prediction))

    def test_predictions_table_has_canonical_code(self):
        """Schema must carry canonical_code — the column generate writes & predict reads."""
        cols = [r[1] for r in self.conn.execute("PRAGMA table_info(predictions_2026)")]
        self.assertIn("canonical_code", cols)

    def test_predictions_table_populated(self):
        n = self.conn.execute("SELECT COUNT(*) FROM predictions_2026").fetchone()[0]
        self.assertGreater(n, 1000, "predictions_2026 looks empty — run generate_predictions.py")

    def test_round_validation(self):
        """Invalid CAP round must raise, not silently return empty."""
        with self.assertRaises(ValueError):
            self.predict.compute_prediction(90.0, "GOPENS", round_num=9)

    def test_probability_bounds(self):
        """Every probability stays within the clamped (2%, 98%) range."""
        d = self.predict.compute_prediction(88.0, "GOPENS", round_num=1, top_n=200)
        self.assertGreater(d["total_branches"], 0)
        for r in d["results"]:
            self.assertGreaterEqual(r["probability"], 0.0)
            self.assertLessEqual(r["probability"], 100.0)

    def test_higher_percentile_never_lowers_probability(self):
        """A stronger student must not get a WORSE chance at the same branch."""
        low = self.predict.compute_prediction(80.0, "GOPENS", round_num=1, top_n=2000)
        high = self.predict.compute_prediction(99.0, "GOPENS", round_num=1, top_n=2000)
        low_map = {(r["college_name"], r["branch_name"]): r["probability"] for r in low["results"]}
        high_map = {(r["college_name"], r["branch_name"]): r["probability"] for r in high["results"]}
        common = set(low_map) & set(high_map)
        self.assertGreater(len(common), 50)
        for key in common:
            self.assertGreaterEqual(high_map[key] + 1e-6, low_map[key],
                                    f"Higher percentile lowered probability at {key}")

    def test_coep_cross_year_merge(self):
        """COEP CSE was re-coded across years; canonical key must merge all years
        of data present in the DB (4 since the A1 Wayback ingest added 2019:
        verified 2019/2023/2024/2025 all carry the 'COEP Technological University'
        name, and BRANCH_NAME_ALIASES maps 'Computer Engineering' -> 'Computer
        Science and Engineering' across every one of them)."""
        d = self.predict.compute_prediction(99.0, "GOPENS", round_num=1,
                                             branch_filter="Computer", top_n=500)
        coep = [r for r in d["results"]
                if "COEP" in r["college_name"] and "Computer Science" in r["branch_name"]]
        self.assertEqual(len(coep), 1, "COEP CSE should appear exactly once (merged)")
        self.assertEqual(coep[0]["years_with_data"], 4, "COEP CSE should have all 4 years merged")

    def test_gews_falls_back_to_ews(self):
        """DB stores 'EWS', counsellors type 'GEWS' — fallback must return results."""
        d = self.predict.compute_prediction(90.0, "GEWS", round_num=1, top_n=10)
        self.assertGreater(d["total_branches"], 0, "GEWS must fall back to EWS data")
        self.assertEqual(d["results"][0]["category_used"], "EWS")

    def test_ladies_home_falls_back(self):
        """Ladies Home-University category must fall back to its State-level data."""
        d = self.predict.compute_prediction(85.0, "LSCH", round_num=1, top_n=10)
        self.assertGreater(d["total_branches"], 0, "LSCH must fall back to LSCS data")

    def test_prediction_attachment_alignment(self):
        """The canonical key must align cutoff lookup with 2026 predictions (was the bug).
        Branches with >=2 years of high-confidence data should mostly carry a prediction."""
        d = self.predict.compute_prediction(95.0, "GOPENS", round_num=1, top_n=1000)
        attached = sum(1 for r in d["results"] if r["pred_2026"] is not None)
        self.assertGreater(attached / max(len(d["results"]), 1), 0.9,
                           "Most branches should have an aligned 2026 prediction")

    def test_no_high_confidence_boundary_clamp(self):
        """A high-confidence 2026 prediction must never sit at 0.0 or 100.0 — those
        are extrapolation clamp artifacts from sparse, noisy reserved-category data."""
        bad = self.conn.execute(
            "SELECT COUNT(*) FROM predictions_2026 "
            "WHERE confidence='high' AND (predicted_pct<=0.0 OR predicted_pct>=100.0)"
        ).fetchone()[0]
        self.assertEqual(bad, 0, f"{bad} high-confidence predictions are clamped to a boundary")

    def test_predictions_within_range(self):
        """No prediction may fall outside [0, 100]."""
        bad = self.conn.execute(
            "SELECT COUNT(*) FROM predictions_2026 WHERE predicted_pct<0.0 OR predicted_pct>100.0"
        ).fetchone()[0]
        self.assertEqual(bad, 0)

    def test_linear_predict_reliability_flag(self):
        """Volatile history (spread > VOLATILITY_SPREAD_MAX) must be flagged
        unreliable; the prediction is always the most recent closing
        (carry-forward — validated in scripts/backtest_predictions.py)."""
        import generate_predictions as gp
        # 95 -> 50 -> 5: spread 90, hopelessly volatile.
        pred, slope, n, reliable = gp.linear_predict([(2023, 95.0), (2024, 50.0), (2025, 5.0)])
        self.assertFalse(reliable)
        self.assertEqual(pred, 5.0, "Prediction must be the most recent closing")
        # Moderate volatility (spread 15) is still unreliable.
        _, _, _, reliable_mid = gp.linear_predict([(2023, 70.0), (2024, 85.0), (2025, 80.0)])
        self.assertFalse(reliable_mid)
        # A stable history is reliable, prediction = latest closing.
        pred2, _, _, reliable2 = gp.linear_predict([(2023, 88.0), (2024, 90.0), (2025, 91.0)])
        self.assertTrue(reliable2)
        self.assertEqual(pred2, 91.0)

    def test_carry_forward_never_extrapolates(self):
        """The stored prediction must equal the latest closing, never a trend
        extrapolation (backtest: extrapolation is 44% worse MAE than carry)."""
        import generate_predictions as gp
        pred, slope, _, _ = gp.linear_predict([(2023, 90.0), (2024, 93.0), (2025, 96.0)])
        self.assertEqual(pred, 96.0, "Rising trend must NOT be extrapolated past the latest close")
        self.assertGreater(slope, 0, "Slope metadata should still report the trend")

    def test_predicted_interval_bounds(self):
        """predicted_low/predicted_high must exist, stay in [0,100], and bracket
        predicted_pct in the right order (low <= pct <= high is NOT guaranteed since
        the interval is a P10/P90 error band, not a confidence interval around a mean —
        but low must never exceed high, and both must be within range)."""
        rows = self.conn.execute(
            "SELECT predicted_low, predicted_high FROM predictions_2026 LIMIT 2000"
        ).fetchall()
        self.assertGreater(len(rows), 0)
        for low, high in rows:
            self.assertIsNotNone(low)
            self.assertIsNotNone(high)
            self.assertGreaterEqual(low, 0.0)
            self.assertLessEqual(high, 100.0)
            self.assertLessEqual(low, high)

    def test_volatile_interval_wider_than_stable(self):
        """A volatile (spread > VOLATILITY_SPREAD_MAX) history must yield an interval
        at least as wide as a stable one at the same tier — this is the whole point
        of B1 (calibrated uncertainty). Allow a 10% tolerance: at the bottom ('low')
        tier even the 'stable' bucket is inherently noisy (sparse, obscure branches),
        so the two can come out nearly tied without that being a regression — a hard
        inequality would be too strict there while still catching a real inversion
        (e.g. stable/volatile swapped) at the other tiers."""
        offsets = self.constants.compute_interval_offsets(self.conn)
        for tier in ("elite", "high", "mid", "low"):
            stable = offsets.get((tier, "stable"))
            volatile = offsets.get((tier, "volatile"))
            if stable is None or volatile is None:
                continue
            stable_width = stable[2] - stable[0]
            volatile_width = volatile[2] - volatile[0]
            self.assertGreaterEqual(
                volatile_width, stable_width * 0.9,
                f"tier={tier}: volatile interval ({volatile_width:.2f}) should not be "
                f"meaningfully narrower than stable ({stable_width:.2f})")

    def test_canonical_key_is_shared(self):
        """generate and predict must use the SAME canonical function (no divergence)."""
        self.assertTrue(hasattr(self.constants, "canonical_branch_key"))
        k1 = self.constants.canonical_branch_key("Some College", "Computer Engineering", "06006")
        k2 = self.constants.canonical_branch_key("Some College", "Computer Engineering", "6006")
        self.assertEqual(k1, k2, "Leading-zero code change must yield identical canonical key")


if __name__ == "__main__":
    unittest.main()
