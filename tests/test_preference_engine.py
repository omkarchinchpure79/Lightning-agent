"""
Engine tests for Phase 4 preference_engine + fee_calculator + seat logic.
Uses REAL data from db/edupath.db (no mocks) and asserts INVARIANTS rather than
specific colleges, so the tests stay valid as data is refreshed.
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

from constants import (  # noqa: E402
    resolve_seat_category, normalize_district, BASE_CATEGORY_VARIANTS,
)
from preference_engine import compute_preference_list, _band  # noqa: E402
import fee_calculator  # noqa: E402
import sqlite3  # noqa: E402

DB = os.path.join(os.path.dirname(__file__), "..", "db", "edupath.db")


class TestSeatResolution(unittest.TestCase):
    def test_home_student_gets_home_then_state(self):
        self.assertEqual(resolve_seat_category("GOPEN", "SPPU", "SPPU"),
                         ["GOPENH", "GOPENS"])

    def test_other_student_gets_other_then_state(self):
        self.assertEqual(resolve_seat_category("GOPEN", "SPPU", "RTMNU"),
                         ["GOPENO", "GOPENS"])

    def test_state_only_category_everywhere(self):
        self.assertEqual(resolve_seat_category("TFWS", "SPPU", "RTMNU"), ["TFWS"])
        self.assertEqual(resolve_seat_category("EWS", "MU", "SUK"), ["EWS"])

    def test_unknown_university_treated_as_other(self):
        # If we can't resolve the student's university, never grant a Home seat.
        self.assertEqual(resolve_seat_category("GOPEN", None, "SPPU"),
                         ["GOPENO", "GOPENS"])

    def test_unknown_base_category_empty(self):
        self.assertEqual(resolve_seat_category("ZZZ", "MU", "MU"), [])

    def test_district_normalisation(self):
        self.assertEqual(normalize_district("BEED"), "Beed")
        self.assertEqual(normalize_district("Haveli Subdistrict"), "Pune")
        self.assertEqual(normalize_district(None, "Pimpri"), "Pune")
        self.assertIsNone(normalize_district(None, None))


class TestFeeCalculator(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.conn = sqlite3.connect(DB)
        cls.with_fee = cls.conn.execute(
            "SELECT college_code FROM college_details WHERE fee_tuition_open IS NOT NULL LIMIT 1"
        ).fetchone()[0]
        cls.no_fee = cls.conn.execute(
            "SELECT college_code FROM college_details "
            "WHERE fee_tuition_open IS NULL AND LENGTH(college_code)=5 LIMIT 1"
        ).fetchone()[0]

    @classmethod
    def tearDownClass(cls):
        cls.conn.close()

    def test_open_more_than_reserved(self):
        op = fee_calculator.compute_fee(self.conn, self.with_fee, "GOPEN")
        sc = fee_calculator.compute_fee(self.conn, self.with_fee, "GSC")
        self.assertTrue(op["available"] and sc["available"])
        self.assertGreater(op["total_annual"], sc["total_annual"])

    def test_fee_never_silently_zero(self):
        # A college without fee data must say so, not return a usable 0.
        r = fee_calculator.compute_fee(self.conn, self.no_fee, "GOPEN")
        self.assertFalse(r["available"])
        self.assertNotIn("total_annual", r)

    def test_unknown_category_unavailable(self):
        r = fee_calculator.compute_fee(self.conn, self.with_fee, "ZZZ")
        self.assertFalse(r["available"])


class TestPreferenceEngine(unittest.TestCase):
    def test_unknown_category_returns_error(self):
        out = compute_preference_list(90, "NOTACAT", "Pune")
        self.assertIn("error", out)

    def test_bands_respect_calibrated_interval(self):
        """Bands (B2) are driven by each row's calibrated predicted_low/predicted_high
        interval, not a fixed +-3 margin: SAFE clears predicted_high, PROBABLE sits
        inside [low, high), REACH sits just below low. A low-confidence SAFE call is
        always downgraded to PROBABLE, whatever its margin."""
        out = compute_preference_list(92.5, "GOPEN", "Pune", branch_preferences=["Computer"])
        for r in out["safe"]:
            self.assertGreaterEqual(r["predicted_close"], 0)  # sanity: row is real
            self.assertNotEqual(r["confidence"], "low")  # low can't be SAFE
            if r["predicted_high"] is not None:
                self.assertGreaterEqual(92.5, r["predicted_high"])
        for r in out["probable"]:
            if r["predicted_low"] is not None and r["predicted_high"] is not None:
                # Either genuinely inside the interval, or a low-confidence
                # would-be-SAFE call downgraded here instead.
                inside = r["predicted_low"] <= 92.5 < r["predicted_high"]
                downgraded_safe = 92.5 >= r["predicted_high"] and r["confidence"] == "low"
                self.assertTrue(inside or downgraded_safe)
        for r in out["reach"]:
            if r["predicted_low"] is not None:
                self.assertLess(92.5, r["predicted_low"])

    def test_band_helper_scales_with_tier_and_volatility(self):
        """The whole point of B2: an elite-stable branch goes SAFE at a tiny positive
        margin (its interval is narrow), while a low-tier volatile branch does NOT go
        SAFE at the OLD fixed +3 margin (its interval is far wider than that)."""
        # Elite, stable, narrow interval (~ +-0.5 like the real elite/stable cell).
        self.assertEqual(_band(97.6, 97.0, 96.5, 97.5, "high"), "SAFE")
        # Same margin (+3) but a low-tier volatile branch with a wide interval:
        # percentile is still well inside [low, high), so it must NOT be SAFE.
        self.assertEqual(_band(53.0, 50.0, 30.0, 75.0, "low"), "PROBABLE")
        # Low confidence always downgrades a would-be-SAFE call.
        self.assertEqual(_band(99.0, 90.0, 85.0, 95.0, "low"), "PROBABLE")

    def test_seat_type_flips_with_home_district(self):
        # Same engine run, two students: a Pune student must see Home seats only at
        # SPPU colleges; a Nagpur student must see those same SPPU colleges as Other.
        pune = compute_preference_list(95, "GOPEN", "Pune", branch_preferences=["Computer"])
        nagp = compute_preference_list(95, "GOPEN", "Nagpur", branch_preferences=["Computer"])
        pune_home = {r["college_code"] for b in ("safe", "probable", "reach")
                     for r in pune[b] if r["seat_type"] == "Home"}
        nagp_home = {r["college_code"] for b in ("safe", "probable", "reach")
                     for r in nagp[b] if r["seat_type"] == "Home"}
        # A Pune student's Home colleges must not be Home for a Nagpur student.
        self.assertTrue(pune_home)  # there is at least one Home option
        self.assertFalse(pune_home & nagp_home)

    def test_home_seats_only_at_student_university(self):
        out = compute_preference_list(95, "GOPEN", "Pune", branch_preferences=["Computer"])
        conn = sqlite3.connect(DB)
        for b in ("safe", "probable", "reach"):
            for r in out[b]:
                if r["seat_type"] == "Home":
                    u = conn.execute(
                        "SELECT university_code FROM college_details WHERE college_code=?",
                        (r["college_code"],)).fetchone()[0]
                    self.assertEqual(u, "SPPU")
        conn.close()

    def test_unresolved_district_grants_no_home(self):
        out = compute_preference_list(90, "GOPEN", "Atlantis")
        self.assertTrue(out["district_unresolved"])
        all_rows = out["safe"] + out["probable"] + out["reach"]
        self.assertTrue(all(r["seat_type"] != "Home" for r in all_rows))

    def test_budget_filter_hides_overbudget_keeps_unknown(self):
        out = compute_preference_list(85, "GOPEN", "Pune", fee_budget=20000)
        for b in ("safe", "probable", "reach"):
            for r in out[b]:
                # kept rows are either within budget or have unknown fee (flagged)
                if r["fee"]["available"]:
                    self.assertLessEqual(r["fee"]["total_annual"], 20000)
                else:
                    self.assertIsNone(r["within_budget"])


if __name__ == "__main__":
    unittest.main()
