import sqlite3
import os
import unittest

DB_PATH = "db/edupath.db"

class TestEduPathDatabase(unittest.TestCase):
    
    @classmethod
    def setUpClass(cls):
        # Check if database exists
        cls.db_exists = os.path.exists(DB_PATH)
        if cls.db_exists:
            cls.conn = sqlite3.connect(DB_PATH)
            cls.cursor = cls.conn.cursor()
            
    @classmethod
    def tearDownClass(cls):
        if cls.db_exists:
            cls.conn.close()

    def test_database_exists(self):
        self.assertTrue(self.db_exists, f"Database file does not exist at {DB_PATH}. Run scripts/load_db.py first.")

    def test_colleges_table(self):
        if not self.db_exists:
            self.skipTest("DB not found")
            
        self.cursor.execute("SELECT COUNT(*) FROM colleges;")
        count = self.cursor.fetchone()[0]
        self.assertGreater(count, 0, "colleges table should not be empty")
        
        # Check Government College of Engineering, Amravati (01002) is present
        self.cursor.execute("SELECT college_name FROM colleges WHERE college_code = '01002';")
        res = self.cursor.fetchone()
        self.assertIsNotNone(res, "College '01002' must exist in database")
        self.assertIn("Amravati", res[0], "College 01002 name should contain 'Amravati'")

    def test_confirmed_data_corrections(self):
        # Locks the user-approved source-data fixes (apply_data_corrections.py) so
        # they cannot silently regress. Checks ALL paired codes — the original bug
        # was the 5-digit active code holding wrong values while the 4-digit was right.
        if not self.db_exists:
            self.skipTest("DB not found")

        # COEP: government + autonomous, on every paired code.
        self.cursor.execute("""
            SELECT cd.college_code, cd.institution_type, cd.is_autonomous
            FROM college_details cd JOIN colleges c USING(college_code)
            WHERE c.college_name LIKE '%COEP Technological University%'
        """)
        coep = self.cursor.fetchall()
        self.assertTrue(coep, "COEP must exist")
        for code, itype, autonomous in coep:
            self.assertEqual(itype, "gov", f"COEP {code} institution_type must be 'gov'")
            self.assertEqual(autonomous, 1, f"COEP {code} is_autonomous must be 1")

        # ICT Matunga (Mumbai): government, on every paired code.
        self.cursor.execute("""
            SELECT cd.college_code, cd.institution_type
            FROM college_details cd JOIN colleges c USING(college_code)
            WHERE c.college_name LIKE '%Institute of Chemical Technology, Matunga%'
        """)
        ict = self.cursor.fetchall()
        self.assertTrue(ict, "ICT Matunga must exist")
        for code, itype in ict:
            self.assertEqual(itype, "gov", f"ICT Matunga {code} institution_type must be 'gov'")

    def test_branches_table(self):
        if not self.db_exists:
            self.skipTest("DB not found")

        self.cursor.execute("SELECT COUNT(*) FROM branches;")
        count = self.cursor.fetchone()[0]
        self.assertGreater(count, 0, "branches table should not be empty")
        
        # Check that branch codes have correct lengths (9 or 10 digits)
        self.cursor.execute("SELECT branch_code FROM branches LIMIT 100;")
        codes = [r[0] for r in self.cursor.fetchall()]
        for code in codes:
            self.assertTrue(len(code) in [8, 9, 10, 11, 12], f"Branch code '{code}' has invalid length {len(code)}")

    def test_cutoffs_range_constraints(self):
        if not self.db_exists:
            self.skipTest("DB not found")
            
        # 1. Percentile range check
        self.cursor.execute("SELECT COUNT(*) FROM cutoffs WHERE percentile < 0.0 OR percentile > 100.0;")
        out_of_bounds_pct = self.cursor.fetchone()[0]
        self.assertEqual(out_of_bounds_pct, 0, f"Found {out_of_bounds_pct} percentile values outside [0, 100]")
        
        # 2. Merit number check
        self.cursor.execute("SELECT COUNT(*) FROM cutoffs WHERE merit_no IS NOT NULL AND merit_no <= 0;")
        invalid_merits = self.cursor.fetchone()[0]
        self.assertEqual(invalid_merits, 0, f"Found {invalid_merits} merit ranks <= 0")

    def test_cutoffs_duplicates(self):
        if not self.db_exists:
            self.skipTest("DB not found")
            
        # Check for duplicates of (year, round, branch_code, seat_type, category, stage, exam_type)
        self.cursor.execute("""
        SELECT year, round, branch_code, seat_type, category, stage, exam_type, COUNT(*) 
        FROM cutoffs 
        WHERE is_all_india = 0
        GROUP BY year, round, branch_code, seat_type, category, stage, exam_type 
        HAVING COUNT(*) > 1;
        """)
        dupes = self.cursor.fetchall()
        self.assertEqual(len(dupes), 0, f"Found duplicate entries in MH cutoffs: {dupes[:5]}")

    def test_no_impossible_percentiles_in_cutoffs(self):
        # CET Cell PDFs contain glitch rows (e.g. TFWS printed "(0.0000000)"
        # against merit 1102 — verified in the 2024 R1 source PDF). load_db.py
        # flags them at load time; apply_data_corrections.py quarantines them
        # from a live DB. If this fails, run apply_data_corrections.py.
        if not self.db_exists:
            self.skipTest("DB not found")
        import sys
        sys.path.insert(0, "scripts")
        from constants import find_impossible_percentile_keys

        rows = self.cursor.execute(
            "SELECT id, year, percentile, merit_no FROM cutoffs WHERE is_all_india = 0"
        ).fetchall()
        bad = find_impossible_percentile_keys(rows)
        self.assertEqual(
            len(bad), 0,
            f"{len(bad)} cutoff rows have a percentile impossible for their "
            f"merit_no (source-PDF glitch) — run apply_data_corrections.py. "
            f"Sample ids: {sorted(bad)[:5]}")

    def test_all_prediction_colleges_have_details(self):
        # The preference engine INNER JOINs predictions_2026 to college_details;
        # a college missing there is silently invisible to every student.
        # populate_university_map.ensure_details_rows() heals this.
        if not self.db_exists:
            self.skipTest("DB not found")
        self.cursor.execute("""
            SELECT COUNT(DISTINCT p.college_code) FROM predictions_2026 p
            LEFT JOIN college_details cd ON cd.college_code = p.college_code
            WHERE cd.college_code IS NULL
        """)
        missing = self.cursor.fetchone()[0]
        self.assertEqual(
            missing, 0,
            f"{missing} colleges have predictions but no college_details row "
            f"(their options are dropped from preference lists) — run "
            f"populate_university_map.py")

    def test_years_and_rounds_loaded(self):
        if not self.db_exists:
            self.skipTest("DB not found")
            
        # Verify years loaded are exactly 2023, 2024, 2025
        self.cursor.execute("SELECT DISTINCT year FROM cutoffs ORDER BY year;")
        years = [r[0] for r in self.cursor.fetchall()]
        self.assertTrue(set([2023, 2024, 2025]).issubset(set(years)), f"Expected years 2023, 2024, 2025. Found: {years}")
        
        # Verify rounds loaded
        self.cursor.execute("SELECT DISTINCT round FROM cutoffs ORDER BY round;")
        rounds = [r[0] for r in self.cursor.fetchall()]
        self.assertTrue(len(rounds) >= 3, f"Expected at least 3 rounds. Found: {rounds}")

if __name__ == "__main__":
    unittest.main()
