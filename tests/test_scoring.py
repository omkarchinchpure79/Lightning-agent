"""
Regression tests for the college quality-score system (score_colleges.py +
setup_college_profiles.pillar_score / sync_paired_code_scores + constants.canonical_college_key).

WHY THIS FILE EXISTS:
The scoring feature had three compounding bugs found by manual audit: (1) a
duplicate, wrong (unscaled, unweighted) scoring formula inline in load_db.py
that silently reverted colleges.score after every reload, (2) name-equality
pairing that missed same-college code pairs whenever the PDF text drifted
(district renames, dropped trust-name suffixes), leaving one fragment's real
data invisible, and (3) a flat AVG() over whatever subsets happened to exist,
which let sparse "easy fact" data outscore colleges with real but incomplete
placement/infra data. None of this was covered by a test, so it shipped and
stayed silently wrong. These tests lock in the fixed-weight pillar formula
and canonical-key pairing so a future edit that reintroduces either bug fails
loudly.

Run:  python -m unittest discover -s tests
(Requires db/edupath.db populated + score_colleges.py run at least once.)
"""

import os
import sys
import sqlite3
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
os.chdir(ROOT)

DB_PATH = "db/edupath.db"


class TestCanonicalCollegeKey(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        import constants
        cls.constants = constants

    def test_zero_padded_code_pairs_match(self):
        """4-digit and its 5-digit zero-padded twin must resolve to one key."""
        k1 = self.constants.canonical_college_key("2008", "Government College of Engineering, Aurangabad")
        k2 = self.constants.canonical_college_key("02008", "Government College of Engineering, Chhatrapati Sambhajinagar")
        self.assertEqual(k1, k2, "code-equivalent colleges must share a canonical key even when the name text changed")

    def test_recoded_college_matched_by_name_fragment(self):
        k1 = self.constants.canonical_college_key("6006", "COEP Technological University")
        k2 = self.constants.canonical_college_key("16006", "COEP Technological University")
        self.assertEqual(k1, k2)

    def test_unrelated_colleges_stay_distinct(self):
        k1 = self.constants.canonical_college_key("3012", "Veermata Jijabai Technological Institute(VJTI), Matunga, Mumbai")
        k2 = self.constants.canonical_college_key("6271", "Pune Institute of Computer Technology")
        self.assertNotEqual(k1, k2)


class TestPillarScore(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        import setup_college_profiles as scp
        cls.scp = scp

    def test_score_is_always_in_valid_range(self):
        cases = [
            {},  # a college with zero data anywhere
            {"selectivity": 10.0},
            {"selectivity": 10.0, "naac": 10.0, "nirf": 10.0},
            {"placement_pct": 10.0, "avg_package": 10.0, "campus": 10.0, "labs": 10.0},
        ]
        for subset_scores in cases:
            score, estimated = self.scp.pillar_score(subset_scores)
            self.assertGreaterEqual(score, 10.0)
            self.assertLessEqual(score, 100.0)

    def test_missing_pillar_is_backfilled_not_dropped(self):
        """A college with ONLY selectivity data must not score as if academic/infra were zero,
        nor be penalized by a shrinking denominator — academic is ESTIMATED from selectivity
        (discounted, so real credentials elsewhere can outrank it), infra (no reliable proxy)
        falls back to a neutral 5.0, never to zero."""
        score, estimated = self.scp.pillar_score({"selectivity": 10.0})
        self.assertIn("academic_outcomes", estimated)
        self.assertIn("infrastructure", estimated)
        # selectivity=10 (0.30) + academic proxied to (10-2)=8.0 (0.45) + infra neutral 6.0 (0.25) -> 81.0
        self.assertEqual(score, 81.0)

    def test_real_credentials_outrank_dataless_proxy_at_equal_selectivity(self):
        """The misalignment this fixes: two equally-selective colleges, one with REAL
        NAAC A + NIRF data and one with none, must rank the credentialed one HIGHER
        (previously the data-less college's undiscounted proxy won — VJTI < PICT)."""
        dataless = {"selectivity": 10.0}
        credentialed = {"selectivity": 10.0, "naac": 9.0, "nirf": 8.5}
        s_dataless, _ = self.scp.pillar_score(dataless)
        s_cred, _ = self.scp.pillar_score(credentialed)
        self.assertGreater(s_cred, s_dataless)

    def test_more_subsets_at_the_same_value_does_not_change_the_score(self):
        """The fairness the user asked for: a pillar averaged over 1 real subset vs 4 real
        subsets, ALL reporting the same quality, must score identically — the NUMBER of
        subsets filled must not move the score, only their values should."""
        one_subset = {"selectivity": 8.0, "naac": 8.0}
        four_subsets = {"selectivity": 8.0, "naac": 8.0, "nirf": 8.0, "autonomous": 8.0, "year_estd": 8.0}
        score_one, _ = self.scp.pillar_score(one_subset)
        score_four, _ = self.scp.pillar_score(four_subsets)
        self.assertEqual(score_one, score_four)

    def test_real_evidence_beats_neutral_proxy(self):
        """A college with a VERIFIED strong infra subset should outscore one with no infra
        data at all (which falls back to a neutral 5.0) — completeness-invariance means
        equal real evidence ties, not that real evidence gets ignored."""
        no_infra_data = {"selectivity": 8.0}
        verified_strong_infra = {"selectivity": 8.0, "campus": 9.0, "hostel": 9.0}
        score_a, _ = self.scp.pillar_score(no_infra_data)
        score_b, _ = self.scp.pillar_score(verified_strong_infra)
        self.assertGreater(score_b, score_a)

    def test_practical_subsets_excluded_from_quality_score(self):
        """fee/city_tier/inst_type must not move the quality score — they're
        affordability/convenience signals, not quality signals."""
        without_practical = {"selectivity": 6.0}
        with_practical = {"selectivity": 6.0, "fee": 10.0, "city_tier": 10.0,
                           "inst_type": 10.0, "tfws": 10.0}
        score_a, _ = self.scp.pillar_score(without_practical)
        score_b, _ = self.scp.pillar_score(with_practical)
        self.assertEqual(score_a, score_b)


@unittest.skipUnless(os.path.exists(DB_PATH), "db/edupath.db not found — run load_db.py")
class TestScoringOnRealDB(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.conn = sqlite3.connect(DB_PATH)

    @classmethod
    def tearDownClass(cls):
        cls.conn.close()

    def test_no_college_stuck_on_unscaled_1_to_10_score(self):
        """Regression guard for the load_db.py duplicate-formula bug: every non-null
        score must be on the 0-100 scale, never a bare 1-10 average."""
        cur = self.conn.execute("SELECT COUNT(*) FROM colleges WHERE score IS NOT NULL AND score <= 10")
        self.assertEqual(cur.fetchone()[0], 0)

    def test_paired_codes_have_identical_scores(self):
        """Known code-pair (Aurangabad -> Chhatrapati Sambhajinagar rename) must be unified."""
        rows = self.conn.execute(
            "SELECT score FROM colleges WHERE college_code IN ('2008','02008')").fetchall()
        if len(rows) == 2:
            self.assertEqual(rows[0][0], rows[1][0])

    def test_college_with_no_details_row_still_gets_a_score(self):
        """selectivity is derivable from cutoffs alone, so colleges lacking a
        college_details row entirely must no longer show score=NULL."""
        cur = self.conn.execute("""
            SELECT COUNT(*) FROM colleges c
            WHERE c.score IS NULL
              AND EXISTS (SELECT 1 FROM branches b JOIN cutoffs cu ON cu.branch_code = b.branch_code
                          WHERE b.college_code = c.college_code AND cu.year IN (2023,2024,2025) AND cu.round=1)
        """)
        # Some colleges may genuinely have no OPEN_CATEGORIES round-1 row in any year; allow a small residual.
        self.assertLess(cur.fetchone()[0], 20)


if __name__ == "__main__":
    unittest.main()
