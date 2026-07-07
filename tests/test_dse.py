"""
test_dse.py — DSE (Direct Second Year) data plane: parsed data spot checks,
prediction generation invariants, and the DSE preference engine.

Spot-check values are read BY EYE from the official PDFs (never from our own
pipeline output), same discipline as test_spot_checks.py:
  - GCOE Amravati (1002) Civil Engineering, choice 100219110:
      2025-26 R1 GOPEN merit 1282 (92.74%)      [dse_cutoff_2025_round1.pdf p.1]
      2023-24 R1 GOPEN merit  393 (93.32%)      [dse_cutoff_2023_round1.pdf p.1]
  - GCOE Yavatmal (1012) Electrical Engineering, choice 101229310, 2025-26 R1:
      LST closed at Stage-II: merit 32963 (75.00%)   [p.5 — the column-alignment case]
      PWDR-OBC Stage-I: merit 29618 (76.39%)
  - GRAMIN T&M CAMPUS NANDED (2508) Computer Engineering, choice 250824510,
      2025-26 R2, p.127: verified by EXACT pdfplumber word x-coordinates
      (category header centers vs merit/pct row centers), not naive reading
      order — GOPEN closes at Stage-I (78.00%) only; GST closes at Stage-VII
      (70.46%) only (GOPEN never appears in the Stage-VII row — a naive
      sequential-position read of the merit numbers would wrongly pair
      Stage-VII's first value with GOPEN rather than its true column, GST).
"""
import os
import sqlite3
import sys
import unittest

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(_ROOT, "scripts"))

from constants import (  # noqa: E402
    DSE_CATEGORY_LEGEND, DSE_CATEGORY_MAP, DSE_VALID_ROUNDS,
)
import dse_engine  # noqa: E402

DB_PATH = os.path.join(_ROOT, "db", "edupath.db")
dse_engine.DB_PATH = DB_PATH


def _conn():
    return sqlite3.connect(DB_PATH)


class TestDseCutoffsData(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.conn = _conn()

    @classmethod
    def tearDownClass(cls):
        cls.conn.close()

    def _one(self, sql, *args):
        return self.conn.execute(sql, args).fetchone()

    def test_table_loaded_with_all_seven_pdfs(self):
        rows = self.conn.execute(
            "SELECT year, round, COUNT(*) FROM dse_cutoffs GROUP BY year, round"
        ).fetchall()
        got = {(y, r) for y, r, _ in rows}
        self.assertEqual(got, {(2023, 1), (2023, 2), (2023, 3),
                               (2024, 1), (2024, 2), (2025, 1), (2025, 2)})
        total = self._one("SELECT COUNT(*) FROM dse_cutoffs")[0]
        self.assertGreater(total, 40000)

    def test_all_categories_in_legend(self):
        cats = {r[0] for r in self.conn.execute("SELECT DISTINCT category FROM dse_cutoffs")}
        self.assertTrue(cats.issubset(DSE_CATEGORY_LEGEND),
                        f"unknown categories loaded: {cats - DSE_CATEGORY_LEGEND}")

    def test_percentages_in_range(self):
        bad = self._one(
            "SELECT COUNT(*) FROM dse_cutoffs WHERE merit_pct < 0 OR merit_pct > 100")[0]
        self.assertEqual(bad, 0)

    def test_spot_gcoe_amravati_civil_2025_r1_gopen(self):
        row = self._one(
            "SELECT merit_no, merit_pct FROM dse_cutoffs WHERE year=2025 AND round=1 "
            "AND choice_code='100219110' AND category='GOPEN' AND stage='I'")
        self.assertIsNotNone(row)
        self.assertEqual(row[0], 1282)
        self.assertAlmostEqual(row[1], 92.74)

    def test_spot_gcoe_amravati_civil_2023_r1_gopen(self):
        row = self._one(
            "SELECT merit_no, merit_pct FROM dse_cutoffs WHERE year=2023 AND round=1 "
            "AND choice_code='100219110' AND category='GOPEN' AND stage='I'")
        self.assertIsNotNone(row)
        self.assertEqual(row[0], 393)
        self.assertAlmostEqual(row[1], 93.32)

    def test_spot_column_alignment_yavatmal_lst_stage2(self):
        """The stage-II row on p.5 covers ONLY the LST column — a reading-order
        parser mis-assigns it; column alignment must land it on LST exactly."""
        row = self._one(
            "SELECT merit_no, merit_pct FROM dse_cutoffs WHERE year=2025 AND round=1 "
            "AND choice_code='101229310' AND category='LST' AND stage='II'")
        self.assertIsNotNone(row)
        self.assertEqual(row[0], 32963)
        self.assertAlmostEqual(row[1], 75.00)
        row = self._one(
            "SELECT merit_no, merit_pct FROM dse_cutoffs WHERE year=2025 AND round=1 "
            "AND choice_code='101229310' AND category='PWDR-OBC' AND stage='I'")
        self.assertIsNotNone(row)
        self.assertEqual(row[0], 29618)
        self.assertAlmostEqual(row[1], 76.39)

    def test_spot_r2_column_alignment_not_reading_order(self):
        """GOPEN (leftmost header column) closes at Stage-I only; GST (3rd
        header column) closes at Stage-VII only, with NO Stage-I value at
        all. A reading-order parser would misassign Stage-VII's first merit
        value (43142) to GOPEN or to GST-by-sequence-position; true column
        alignment must land it on GST specifically."""
        gopen = dict(self.conn.execute(
            "SELECT stage, merit_pct FROM dse_cutoffs WHERE year=2025 AND round=2 "
            "AND choice_code='250824510' AND category='GOPEN'").fetchall())
        self.assertEqual(set(gopen), {"I"})
        self.assertAlmostEqual(gopen["I"], 78.00)

        gst = dict(self.conn.execute(
            "SELECT stage, merit_pct FROM dse_cutoffs WHERE year=2025 AND round=2 "
            "AND choice_code='250824510' AND category='GST'").fetchall())
        self.assertEqual(set(gst), {"VII"})
        self.assertAlmostEqual(gst["VII"], 70.46)

    def test_dse_never_mixed_into_fe_cutoffs(self):
        """DSE percentages must never leak into the FE cutoffs table: no FE row
        may carry a DSE-only category code."""
        dse_only = DSE_CATEGORY_LEGEND - {"EWS"}  # EWS exists in both worlds
        qs = ",".join("?" * len(dse_only))
        n = self._one(
            f"SELECT COUNT(*) FROM cutoffs WHERE category IN ({qs})", *dse_only)[0]
        self.assertEqual(n, 0)


class TestDsePredictions(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.conn = _conn()

    @classmethod
    def tearDownClass(cls):
        cls.conn.close()

    def test_predictions_exist_for_valid_rounds_only(self):
        rounds = {r[0] for r in self.conn.execute("SELECT DISTINCT round FROM dse_predictions")}
        self.assertEqual(rounds, set(DSE_VALID_ROUNDS))

    def test_carry_forward_matches_latest_year_close(self):
        """predicted_pct must equal the newest year's MIN(merit_pct) for the
        same choice_code+category+round (carry-forward model, no extrapolation)."""
        rows = self.conn.execute(
            "SELECT branch_code, category, round, predicted_pct FROM dse_predictions "
            "ORDER BY canonical_code LIMIT 50").fetchall()
        self.assertTrue(rows)
        for choice, cat, rnd, predicted in rows:
            actual = self.conn.execute(
                "SELECT MIN(merit_pct) FROM dse_cutoffs WHERE choice_code=? AND "
                "category=? AND round=? AND year=(SELECT MAX(year) FROM dse_cutoffs "
                "WHERE choice_code=? AND category=? AND round=?)",
                (choice, cat, rnd, choice, cat, rnd)).fetchone()[0]
            self.assertIsNotNone(actual)
            self.assertAlmostEqual(predicted, actual, places=2)

    def test_confidence_values_valid(self):
        vals = {r[0] for r in self.conn.execute("SELECT DISTINCT confidence FROM dse_predictions")}
        self.assertTrue(vals.issubset({"high", "medium", "low"}))


class TestDseEngine(unittest.TestCase):
    def test_bands_returned_for_open_student(self):
        out = dse_engine.compute_dse_preference_list(88.0, "GOPEN", round_num=1)
        self.assertNotIn("error", out)
        self.assertEqual(out["admission_type"], "dse")
        total = out["counts"]["safe"] + out["counts"]["probable"] + out["counts"]["reach"]
        self.assertGreater(total, 0)
        for row in out["safe"][:5]:
            self.assertEqual(row["category_used"], "GOPEN")
            self.assertEqual(row["seat_type"], "DSE")
            self.assertAlmostEqual(row["margin"], round(88.0 - row["predicted_close"], 2))

    def test_vj_maps_to_nta(self):
        out = dse_engine.compute_dse_preference_list(80.0, "GVJ", round_num=1)
        self.assertNotIn("error", out)
        rows = out["safe"] + out["probable"] + out["reach"]
        self.assertTrue(rows)
        self.assertTrue(all(r["category_used"] == "GNTA" for r in rows))

    def test_tfws_fails_explicit(self):
        out = dse_engine.compute_dse_preference_list(90.0, "TFWS", round_num=1)
        self.assertIn("error", out)
        self.assertIn("no seat quota in DSE", out["error"])

    def test_round_3_fails_explicit(self):
        out = dse_engine.compute_dse_preference_list(90.0, "GOPEN", round_num=3)
        self.assertIn("error", out)
        self.assertIn("round 3", out["error"])

    def test_unknown_category_fails_explicit(self):
        out = dse_engine.compute_dse_preference_list(90.0, "NOTACAT", round_num=1)
        self.assertIn("error", out)

    def test_adapter_sets_entry_key_and_no_pools(self):
        sys.path.insert(0, os.path.join(_ROOT, "app"))
        import engine_adapter as ea
        out = ea.dse_preference_list(85.0, "GOPEN", round_num=1, top_per_band=5)
        self.assertNotIn("error", out)
        for band in ("safe", "probable", "reach"):
            for row in out[band]:
                self.assertEqual(row["entry_key"], row["canonical_code"])
                self.assertIsNone(row["seat_pool"])
                self.assertEqual(row["seat_data_status"], "exact")


if __name__ == "__main__":
    unittest.main()
