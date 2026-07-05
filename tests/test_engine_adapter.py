"""
Tests for app/engine_adapter.py — the Phase 5 contract boundary.
Asserts the adapter maps inputs correctly and returns the engine dicts intact,
regardless of working directory (it pins an absolute DB path).
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "app"))
import engine_adapter as ea  # noqa: E402


class TestEngineAdapter(unittest.TestCase):
    def test_category_label_to_code(self):
        self.assertEqual(ea.category_code("General — Open"), "GOPEN")
        self.assertEqual(ea.category_code("Ladies — OBC"), "LOBC")
        self.assertEqual(ea.category_code("TFWS (Tuition Fee Waiver)"), "TFWS")
        # Forgiving: a raw code passes through unchanged.
        self.assertEqual(ea.category_code("GOPEN"), "GOPEN")

    def test_all_category_codes_are_known_to_engine(self):
        from constants import BASE_CATEGORY_VARIANTS
        for label in ea.category_labels():
            self.assertIn(ea.category_code(label), BASE_CATEGORY_VARIANTS,
                          f"{label} maps to an unknown base category")

    def test_districts_nonempty_no_mumbai_dupes(self):
        ds = ea.list_districts()
        self.assertGreater(len(ds), 30)
        self.assertEqual(ds.count("Mumbai"), 1)
        self.assertNotIn("Mumbai City", ds)

    def test_db_path_is_absolute_and_exists(self):
        self.assertTrue(os.path.isabs(ea.db_path()))
        self.assertTrue(os.path.exists(ea.db_path()))

    def test_preference_list_returns_contract(self):
        out = ea.preference_list(92.5, "General — Open", "Pune",
                                 branch_preferences=["Computer"], top_per_band=3)
        for key in ("safe", "probable", "reach", "counts", "district_unresolved"):
            self.assertIn(key, out)
        if out["safe"]:
            row = out["safe"][0]
            for key in ("college_name", "seat_type", "predicted_close", "band", "fee"):
                self.assertIn(key, row)

    def test_eligibility_flags_off_leave_output_unchanged(self):
        """C1 must be additive: no flags set -> identical to the pre-C1 behaviour,
        and every row is tagged seat_pool=None (never missing the key)."""
        plain = ea.preference_list(90, "General — Open", "Pune")
        again = ea.preference_list(90, "General — Open", "Pune",
                                   tfws_eligible=False, defense_status=False,
                                   pwd_status=False, orphan_status=False,
                                   family_income_bracket=None)
        self.assertEqual(plain, again)
        for band in ("safe", "probable", "reach"):
            for row in plain[band]:
                self.assertIsNone(row["seat_pool"])

    def test_tfws_eligible_surfaces_tfws_pool(self):
        """A TFWS-eligible student must see TFWS-pool rows merged into their bands
        (Fix C1) -- these seats were previously invisible even though the engine
        has always been able to compute them for the TFWS base category."""
        base = ea.preference_list(90, "General — Open", "Pune")
        with_tfws = ea.preference_list(90, "General — Open", "Pune", tfws_eligible=True)
        tfws_rows = [r for b in ("safe", "probable", "reach") for r in with_tfws[b]
                     if r["seat_pool"] == "TFWS"]
        self.assertTrue(tfws_rows, "TFWS-eligible student should see at least one TFWS row")
        base_total = sum(len(base[b]) for b in ("safe", "probable", "reach"))
        with_total = sum(len(with_tfws[b]) for b in ("safe", "probable", "reach"))
        self.assertGreaterEqual(with_total, base_total)

    def test_pool_rows_are_distinct_selectable_entries(self):
        """A pool seat (e.g. TFWS's separate quota) is a genuinely different seat
        the counsellor can shortlist independently of the general seat, so the
        same branch may appear as BOTH a general entry and a TFWS entry
        (counsellor request 2026-07-05). Identity is entry_key (canonical_code +
        seat_pool), which must be unique; canonical_code alone may repeat."""
        out = ea.preference_list(90, "General — Open", "Pune", tfws_eligible=True)
        keys = [r["entry_key"] for b in ("safe", "probable", "reach") for r in out[b]]
        self.assertEqual(len(keys), len(set(keys)),
                         "entry_key must be unique across the merged bands")
        # A TFWS entry's entry_key is canonical_code + '::TFWS' and is distinct
        # from the general entry's plain canonical_code for the same branch.
        tfws = [r for b in ("safe", "probable", "reach") for r in out[b]
                if r["seat_pool"] == "TFWS"]
        self.assertTrue(tfws, "TFWS-eligible student should see TFWS entries")
        for r in tfws:
            self.assertEqual(r["entry_key"], f"{r['canonical_code']}::TFWS")

    def test_round_strategy_and_profile_and_fee(self):
        rs = ea.round_strategy(94, "General — Open", "Pune", ["Computer"])
        self.assertIn("results", rs)
        self.assertTrue(rs["results"])
        self.assertIn("advice_code", rs["results"][0])

        prof = ea.college_profile(rs["results"][0]["college_code"])
        self.assertIn("cutoff_trends", prof)
        self.assertIn("fees", prof)

        fee = ea.fee_for("02008", "Ladies — OBC")
        self.assertTrue(fee["available"])
        self.assertGreater(fee["total_annual"], 0)


if __name__ == "__main__":
    unittest.main()
