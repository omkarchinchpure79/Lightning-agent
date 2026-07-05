"""
Regression tests for parse_seat_intake.py.

WHY THIS FILE EXISTS: the first version of the classifier folded EWS entries
into the same bucket as the base/general entry, which produced a false
"conflict" (two genuinely different Sanction Intake numbers landing on the
same canonical_code+bucket key) for almost every branch with an EWS quota.
Locking in the classification + the known-correct numbers for a
hand-verified college (Institute of Chemical Technology, Matunga — 03036)
so this can't silently regress.

Requires data/raw/pdfs/seat_intake/CAPR-I_03036.pdf (downloaded by
download_seat_intake_pdfs.py) — skipped if not present.
"""
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
os.chdir(ROOT)

import parse_seat_intake as psi  # noqa: E402

SAMPLE_PDF = os.path.join("data", "raw", "pdfs", "seat_intake", "CAPR-I_03036.pdf")


class TestClassify(unittest.TestCase):
    def test_base_course_code_is_general(self):
        self.assertEqual(psi._classify("", None), "general")

    def test_ews_tag_is_its_own_bucket_not_general(self):
        """The bug this file guards against: EWS must NOT collapse into 'general'."""
        self.assertEqual(psi._classify("", "EWS"), "ews")

    def test_trailing_t_is_tfws(self):
        self.assertEqual(psi._classify("T", None), "tfws")


@unittest.skipUnless(os.path.exists(SAMPLE_PDF), "seat-intake PDF corpus not downloaded")
class TestParsePdfKnownCollege(unittest.TestCase):
    """Institute of Chemical Technology, Matunga — hand-verified against the
    source PDF text during development (conversation notes 2026-07-05)."""

    @classmethod
    def setUpClass(cls):
        cls.parsed, cls.anomalies = psi.parse_pdf(
            SAMPLE_PDF, "03036", "Institute of Chemical Technology, Matunga, Mumbai"
        )

    def test_no_anomalies(self):
        self.assertEqual(self.anomalies, [])

    def test_chemical_engineering_general_and_tfws_intake(self):
        import constants
        key = constants.canonical_branch_key(
            "Institute of Chemical Technology, Matunga, Mumbai", "Chemical Engineering", "0303650710"
        )
        self.assertIn(key, self.parsed)
        entry = self.parsed[key]
        self.assertEqual(entry["general"], 75)
        self.assertEqual(entry["tfws"], 4)
        self.assertEqual(entry["ews"], 8)

    def test_every_parsed_branch_has_a_name(self):
        for entry in self.parsed.values():
            self.assertTrue(entry["branch_name"])


DBATU_PDF = os.path.join("data", "raw", "pdfs", "seat_intake", "CAPR-I_03033.pdf")


@unittest.skipUnless(os.path.exists(DBATU_PDF), "seat-intake PDF corpus not downloaded")
class TestParsePdfRegionalQuotaSumming(unittest.TestCase):
    """
    Dr. Babasaheb Ambedkar Technological University, Lonere (03033) has a
    Konkan-region quota sub-pool ("...13K" course code) alongside the base
    entry for Civil Engineering — the exact case that used to get miscoded as
    a "conflict" (46 vs 8) before general/tfws became sums-of-sub-pools
    instead of first-value-wins. Numbers hand-verified against the source PDF.
    """

    @classmethod
    def setUpClass(cls):
        cls.parsed, cls.anomalies = psi.parse_pdf(
            DBATU_PDF, "03033", "Dr. Babasaheb Ambedkar Technological University, Lonere"
        )

    def test_no_anomalies(self):
        self.assertEqual(self.anomalies, [])

    def test_konkan_quota_adds_into_general_not_a_conflict(self):
        import constants
        key = constants.canonical_branch_key(
            "Dr. Babasaheb Ambedkar Technological University, Lonere",
            "Civil Engineering", "0303319110"
        )
        entry = self.parsed[key]
        self.assertEqual(entry["general"], 46 + 8)  # base 46 + Konkan-quota 8
        self.assertEqual(entry["tfws"], 3)
        self.assertEqual(entry["ews"], 5)


if __name__ == "__main__":
    unittest.main()
