"""
setup_college_profiles.py
Adds Y-set tables to edupath.db without touching existing cutoff/college/branch data.
Safe to run multiple times — migrations are handled automatically.

Tables added/managed:
  college_details       -- full profile data for each college (Y set)
  college_subset_scores -- individual 1-10 scores per subset per college
  home_university_map   -- Maharashtra district -> university mapping
  predictions_2026      -- predicted 2026 closing cutoffs per branch/category/round
  subset_definitions    -- the 20 scoring subsets and their display labels
"""

import sqlite3
import os

from constants import TOTAL_SUBSETS, ensure_predictions_table

DB_PATH = "db/edupath.db"

HOME_UNIVERSITY_DATA = [
    # University of Mumbai (MU) — 7 districts
    ("Mumbai City",               "MU",     "University of Mumbai"),
    ("Mumbai Suburban",           "MU",     "University of Mumbai"),
    ("Thane",                     "MU",     "University of Mumbai"),
    ("Palghar",                   "MU",     "University of Mumbai"),
    ("Raigad",                    "MU",     "University of Mumbai"),
    ("Ratnagiri",                 "MU",     "University of Mumbai"),
    ("Sindhudurg",                "MU",     "University of Mumbai"),
    # Savitribai Phule Pune University (SPPU) — 3 districts ONLY
    # Kolhapur/Sangli/Satara are SUK — a separate H-seat bucket in CAP
    ("Pune",                      "SPPU",   "Savitribai Phule Pune University"),
    ("Nashik",                    "SPPU",   "Savitribai Phule Pune University"),
    ("Ahmednagar",                "SPPU",   "Savitribai Phule Pune University"),
    # Shivaji University, Kolhapur (SUK) — 3 districts
    # Distinct from SPPU: Sangli student gets H-seats at SUK colleges, NOT SPPU colleges
    ("Kolhapur",                  "SUK",    "Shivaji University, Kolhapur"),
    ("Sangli",                    "SUK",    "Shivaji University, Kolhapur"),
    ("Satara",                    "SUK",    "Shivaji University, Kolhapur"),
    # Solapur University (SolU) — 1 district, separate from both SPPU and SUK
    ("Solapur",                   "SolU",   "Solapur University"),
    # Rashtrasant Tukadoji Maharaj Nagpur University (RTMNU) — 6 districts
    ("Nagpur",                    "RTMNU",  "Rashtrasant Tukadoji Maharaj Nagpur University"),
    ("Wardha",                    "RTMNU",  "Rashtrasant Tukadoji Maharaj Nagpur University"),
    ("Chandrapur",                "RTMNU",  "Rashtrasant Tukadoji Maharaj Nagpur University"),
    ("Gadchiroli",                "RTMNU",  "Rashtrasant Tukadoji Maharaj Nagpur University"),
    ("Gondia",                    "RTMNU",  "Rashtrasant Tukadoji Maharaj Nagpur University"),
    ("Bhandara",                  "RTMNU",  "Rashtrasant Tukadoji Maharaj Nagpur University"),
    # Dr. Babasaheb Ambedkar Marathwada University (BAMU), Chh. Sambhajinagar — 4 districts
    # Both old and new district names kept for backward compatibility with PDF data
    ("Chhatrapati Sambhajinagar", "BAMU",   "Dr. Babasaheb Ambedkar Marathwada University"),
    ("Aurangabad",                "BAMU",   "Dr. Babasaheb Ambedkar Marathwada University"),
    ("Jalna",                     "BAMU",   "Dr. Babasaheb Ambedkar Marathwada University"),
    ("Beed",                      "BAMU",   "Dr. Babasaheb Ambedkar Marathwada University"),
    ("Dharashiv",                 "BAMU",   "Dr. Babasaheb Ambedkar Marathwada University"),
    ("Osmanabad",                 "BAMU",   "Dr. Babasaheb Ambedkar Marathwada University"),
    # Swami Ramanand Teerth Marathwada University (SRTMUN), Nanded — 4 districts
    # Distinct H-seat region from BAMU (confirmed against official CAP jurisdiction)
    ("Nanded",                    "SRTMUN", "Swami Ramanand Teerth Marathwada University"),
    ("Latur",                     "SRTMUN", "Swami Ramanand Teerth Marathwada University"),
    ("Parbhani",                  "SRTMUN", "Swami Ramanand Teerth Marathwada University"),
    ("Hingoli",                   "SRTMUN", "Swami Ramanand Teerth Marathwada University"),
    # Sant Gadge Baba Amravati University (SGBAU) — 5 districts
    ("Amravati",                  "SGBAU",  "Sant Gadge Baba Amravati University"),
    ("Akola",                     "SGBAU",  "Sant Gadge Baba Amravati University"),
    ("Buldhana",                  "SGBAU",  "Sant Gadge Baba Amravati University"),
    ("Washim",                    "SGBAU",  "Sant Gadge Baba Amravati University"),
    ("Yavatmal",                  "SGBAU",  "Sant Gadge Baba Amravati University"),
    # Kavayitri Bahinabai Chaudhari North Maharashtra University (KBCNMU) — 3 districts
    ("Jalgaon",                   "KBCNMU", "Kavayitri Bahinabai Chaudhari North Maharashtra University"),
    ("Dhule",                     "KBCNMU", "Kavayitri Bahinabai Chaudhari North Maharashtra University"),
    ("Nandurbar",                 "KBCNMU", "Kavayitri Bahinabai Chaudhari North Maharashtra University"),
    # "Mumbai" as a plain city name (some college names use it without City/Suburban qualifier)
    ("Mumbai",                    "MU",     "University of Mumbai"),
]

SUBSET_DEFINITIONS = [
    # Academic
    ("naac",            "NAAC Grade/Score",         "academic"),
    ("nirf",            "NIRF Ranking",              "academic"),
    ("nba",             "NBA Accreditation",         "academic"),
    ("autonomous",      "Autonomous Status",         "academic"),
    ("affiliation",     "University Affiliation",    "academic"),
    ("year_estd",       "Year Established",          "academic"),
    # Placement
    ("placement_pct",   "Placement Percentage",      "placement"),
    ("avg_package",     "Average Package (LPA)",     "placement"),
    ("highest_package", "Highest Package (LPA)",     "placement"),
    ("recruiters",      "Top Recruiters",            "placement"),
    # Infrastructure
    ("campus",          "Campus Size",               "infrastructure"),
    ("labs",            "Labs Quality",              "infrastructure"),
    ("hostel",          "Hostel Availability",       "infrastructure"),
    ("sports",          "Sports Facilities",         "infrastructure"),
    ("internet",        "Internet/Smart Classrooms", "infrastructure"),
    # Financial
    ("fee",             "Annual Tuition Fee",        "financial"),
    ("tfws",            "TFWS Seats Available",      "financial"),
    ("scholarships",    "Scholarship Programs",      "financial"),
    # Location & Type
    ("city_tier",       "City Tier",                 "location"),
    ("inst_type",       "Institution Type",          "location"),
]

assert len(SUBSET_DEFINITIONS) == TOTAL_SUBSETS, \
    f"SUBSET_DEFINITIONS has {len(SUBSET_DEFINITIONS)} entries but TOTAL_SUBSETS={TOTAL_SUBSETS} in constants.py — update one of them."


def setup(conn):
    cur = conn.cursor()

    # Enable WAL mode for better concurrent read performance (Phase 5: 3 simultaneous users)
    conn.execute("PRAGMA journal_mode=WAL")

    # Ensure completeness column exists (added after initial schema — safe on fresh and existing DBs)
    try:
        cur.execute("ALTER TABLE colleges ADD COLUMN completeness REAL")
        print("  Added completeness column to colleges.")
    except sqlite3.OperationalError:
        pass  # already exists

    cur.execute("""
    CREATE TABLE IF NOT EXISTS home_university_map (
        district        TEXT PRIMARY KEY,
        university_code TEXT NOT NULL,
        university_name TEXT NOT NULL
    )
    """)

    # college_details migration: recreate if missing university_code column or FOREIGN KEY
    cur.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='college_details'")
    row = cur.fetchone()
    existing_ddl = row[0] if row else ""
    needs_migration = row and (
        "university_code" not in existing_ddl or
        "FOREIGN KEY" not in existing_ddl
    )
    if needs_migration:
        cur.execute("SELECT COUNT(*) FROM college_details")
        existing_rows = cur.fetchone()[0]
        if existing_rows > 0:
            # Preserve data: rename old, copy into new, drop old
            cur.execute("ALTER TABLE college_details RENAME TO college_details_backup")
            print(f"  college_details had {existing_rows} rows — backed up as college_details_backup.")
        else:
            cur.execute("DROP TABLE college_details")
        print("  Migrated college_details: added university_code column and FOREIGN KEY constraint.")

    cur.execute("""
    CREATE TABLE IF NOT EXISTS college_details (
        college_code            TEXT PRIMARY KEY,
        university_code         TEXT,
        -- Academic
        naac_grade              TEXT,
        naac_score              REAL,
        nirf_rank               INTEGER,
        nba_branches            TEXT,
        is_autonomous           INTEGER DEFAULT 0,
        affiliated_university   TEXT,
        year_established        INTEGER,
        -- Institution
        institution_type        TEXT,
        management_name         TEXT,
        -- Financial (fee_tuition_open is FRA-approved tuition for Open/General category;
        --  OBC/SEBC = tuition/2, TFWS = tuition waived, SC/ST pvt = 19000 fixed)
        fee_tuition_open        INTEGER,
        fee_development         INTEGER,
        fee_source              TEXT,
        annual_fee_min          REAL,
        annual_fee_max          REAL,
        tfws_available          INTEGER DEFAULT 0,
        -- Infrastructure
        campus_area_acres       REAL,
        has_hostel_boys         INTEGER,
        has_hostel_girls        INTEGER,
        has_sports              INTEGER,
        has_wifi                INTEGER,
        -- Placements
        placement_pct           REAL,
        placement_reliable      INTEGER DEFAULT 0,
        avg_package_lpa         REAL,
        highest_package_lpa     REAL,
        median_salary_lpa       REAL,
        top_recruiters          TEXT,
        placement_source        TEXT,
        -- Location
        address                 TEXT,
        district                TEXT,
        nearest_railway_km      REAL,
        -- Media
        website_url             TEXT,
        image_urls              TEXT,
        video_url               TEXT,
        principal_name          TEXT,
        -- Meta
        data_source             TEXT,
        last_updated            TEXT,
        notes                   TEXT,
        FOREIGN KEY (college_code) REFERENCES colleges(college_code)
    )
    """)

    # Restore data if we backed it up
    cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='college_details_backup'")
    if cur.fetchone():
        cur.execute("""
            INSERT INTO college_details (college_code, naac_grade, naac_score, nirf_rank,
                nba_branches, is_autonomous, affiliated_university, year_established,
                institution_type, management_name, fee_tuition_open, fee_development,
                fee_source, annual_fee_min, annual_fee_max,
                tfws_available, campus_area_acres, has_hostel_boys, has_hostel_girls,
                has_sports, has_wifi, placement_pct, placement_reliable, avg_package_lpa,
                highest_package_lpa, median_salary_lpa, top_recruiters, placement_source,
                address, nearest_railway_km,
                website_url, image_urls, video_url, principal_name, data_source,
                last_updated, notes)
            SELECT college_code, naac_grade, naac_score, nirf_rank,
                nba_branches, is_autonomous, affiliated_university, year_established,
                institution_type, management_name,
                CASE WHEN fee_tuition_open IS NOT NULL THEN fee_tuition_open ELSE NULL END,
                CASE WHEN fee_development IS NOT NULL THEN fee_development ELSE NULL END,
                CASE WHEN fee_source IS NOT NULL THEN fee_source ELSE NULL END,
                annual_fee_min, annual_fee_max,
                tfws_available, campus_area_acres, has_hostel_boys, has_hostel_girls,
                has_sports, has_wifi, placement_pct,
                CASE WHEN placement_reliable IS NOT NULL THEN placement_reliable ELSE 0 END,
                avg_package_lpa,
                highest_package_lpa,
                CASE WHEN median_salary_lpa IS NOT NULL THEN median_salary_lpa ELSE NULL END,
                top_recruiters, placement_source,
                address, nearest_railway_km,
                website_url, image_urls, video_url, principal_name, data_source,
                last_updated, notes
            FROM college_details_backup
        """)
        cur.execute("DROP TABLE college_details_backup")
        print("  Restored existing college_details data into new schema.")

    # subset_definitions must exist before college_subset_scores (which references it)
    cur.execute("""
    CREATE TABLE IF NOT EXISTS subset_definitions (
        subset_name     TEXT PRIMARY KEY,
        display_label   TEXT NOT NULL,
        category        TEXT NOT NULL
    )
    """)

    # Migrate college_subset_scores: drop if it has old redundant 'category' column
    cur.execute("PRAGMA table_info(college_subset_scores)")
    cols = [r[1] for r in cur.fetchall()]
    if "category" in cols:
        cur.execute("DROP TABLE college_subset_scores")
        print("  Migrated college_subset_scores: removed redundant category column.")

    cur.execute("""
    CREATE TABLE IF NOT EXISTS college_subset_scores (
        id              INTEGER PRIMARY KEY AUTOINCREMENT,
        college_code    TEXT NOT NULL REFERENCES colleges(college_code),
        subset_name     TEXT NOT NULL REFERENCES subset_definitions(subset_name),
        score           REAL NOT NULL CHECK(score >= 1.0 AND score <= 10.0),
        source          TEXT NOT NULL DEFAULT 'manual',
        UNIQUE(college_code, subset_name)
    )
    """)

    # predictions_2026 schema lives in constants.ensure_predictions_table (single
    # source of truth) so it can never drift from generate_predictions.py again.
    if ensure_predictions_table(conn):
        print("  Migrated predictions_2026: added canonical_code/predicted_low/predicted_high "
              "columns (regenerate with generate_predictions.py).")

    # Per-field data provenance: which source each college_details field came from.
    cur.execute("""
    CREATE TABLE IF NOT EXISTS college_data_sources (
        college_code   TEXT NOT NULL,
        field_name     TEXT NOT NULL,
        source_type    TEXT NOT NULL,
        source_url     TEXT,
        is_official    INTEGER DEFAULT 0,
        retrieved_date TEXT,
        PRIMARY KEY (college_code, field_name),
        FOREIGN KEY (college_code) REFERENCES colleges(college_code)
    )
    """)

    # Scrape checkpoint: one row per college, tracks URL discovery + scrape status.
    # status: pending | in_progress | done | failed
    cur.execute("""
    CREATE TABLE IF NOT EXISTS scrape_progress (
        college_code     TEXT PRIMARY KEY,
        college_name     TEXT,
        shiksha_url      TEXT,
        collegedunia_url TEXT,
        wikipedia_url    TEXT,
        shiksha_scraped  INTEGER DEFAULT 0,
        official_scraped INTEGER DEFAULT 0,
        wikipedia_scraped INTEGER DEFAULT 0,
        last_attempted   TEXT,
        status           TEXT DEFAULT 'pending'
    )
    """)
    # Add new columns to scrape_progress if they don't exist yet (safe migration)
    cur.execute("PRAGMA table_info(scrape_progress)")
    sp_cols = {r[1] for r in cur.fetchall()}
    for col_def in [("wikipedia_url", "TEXT"), ("wikipedia_scraped", "INTEGER DEFAULT 0")]:
        if col_def[0] not in sp_cols:
            cur.execute(f"ALTER TABLE scrape_progress ADD COLUMN {col_def[0]} {col_def[1]}")

    # New location columns added for multi-source scraper
    cur.execute("PRAGMA table_info(college_details)")
    cd_cols = {r[1] for r in cur.fetchall()}
    for col, typ in [("latitude", "REAL"), ("longitude", "REAL"), ("google_maps_url", "TEXT")]:
        if col not in cd_cols:
            cur.execute(f"ALTER TABLE college_details ADD COLUMN {col} {typ}")
            print(f"  Added {col} column to college_details.")

    # Fee + placement columns (added after initial schema)
    cur.execute("PRAGMA table_info(college_details)")
    cd_cols = {r[1] for r in cur.fetchall()}
    new_cols = [
        ("fee_tuition_open",    "INTEGER"),
        ("fee_development",     "INTEGER"),
        ("fee_source",          "TEXT"),
        ("placement_reliable",  "INTEGER DEFAULT 0"),
        ("median_salary_lpa",   "REAL"),
        ("top_recruiters",      "TEXT"),
        ("placement_source",    "TEXT"),
        ("phone",               "TEXT"),
        ("email",               "TEXT"),
        ("principal_name",      "TEXT"),
        ("management_name",     "TEXT"),
        # image_metadata stores labeled images: [{url, type, caption, source}]
        # type = "building" | "campus" | "logo" | "infrastructure" | "aerial"
        ("image_metadata",      "TEXT"),
    ]
    for col, typ in new_cols:
        if col not in cd_cols:
            cur.execute(f"ALTER TABLE college_details ADD COLUMN {col} {typ}")
            print(f"  Added {col} column to college_details.")

    print("Tables created (or already exist).")

    cur.executemany(
        "INSERT OR REPLACE INTO home_university_map (district, university_code, university_name) VALUES (?,?,?)",
        HOME_UNIVERSITY_DATA
    )
    print(f"Home university map: {len(HOME_UNIVERSITY_DATA)} districts seeded.")

    # INSERT OR REPLACE so label changes in SUBSET_DEFINITIONS propagate on re-run
    cur.executemany(
        "INSERT OR REPLACE INTO subset_definitions (subset_name, display_label, category) VALUES (?,?,?)",
        SUBSET_DEFINITIONS
    )
    print(f"Subset definitions: {len(SUBSET_DEFINITIONS)} subsets seeded.")

    conn.commit()


def populate_university_codes(conn):
    """
    Auto-fill college_details.university_code from colleges.city -> home_university_map.
    Only fills rows where university_code is currently NULL.
    Call this after Phase 3 data entry or after adding new college_details rows.
    Returns count of colleges updated.
    """
    cur = conn.cursor()
    cur.execute("""
        UPDATE college_details
        SET university_code = (
            SELECT hum.university_code
            FROM colleges c
            JOIN home_university_map hum ON LOWER(c.city) = LOWER(hum.district)
            WHERE c.college_code = college_details.college_code
        )
        WHERE university_code IS NULL
          AND EXISTS (
            SELECT 1 FROM colleges c
            JOIN home_university_map hum ON LOWER(c.city) = LOWER(hum.district)
            WHERE c.college_code = college_details.college_code
          )
    """)
    updated = cur.rowcount
    conn.commit()
    if updated:
        print(f"  Auto-filled university_code for {updated} colleges from city mapping.")
    return updated


def compute_college_scores(conn):
    """
    Recompute overall college score and data completeness from college_subset_scores.
    Score = average of all subset scores scaled to 0-100 (raw 1-10 average × 10).
    Completeness = (subsets scored / TOTAL_SUBSETS) * 100.
    Updates colleges.score and colleges.completeness.
    """
    cur = conn.cursor()

    cur.execute("""
        SELECT college_code, AVG(score), COUNT(score)
        FROM college_subset_scores
        GROUP BY college_code
    """)
    rows = cur.fetchall()

    updated = 0
    for college_code, avg_score, count in rows:
        completeness = round(count / TOTAL_SUBSETS * 100, 1)
        cur.execute(
            "UPDATE colleges SET score = ?, completeness = ? WHERE college_code = ?",
            (round(avg_score * 10, 1), completeness, college_code)
        )
        updated += 1

    conn.commit()
    print(f"Recomputed scores for {updated} colleges.")
    sync_paired_code_scores(conn)
    return updated


def sync_paired_code_scores(conn):
    """
    The same physical college holds subset scores under BOTH its legacy 4-digit
    and current 5-digit code, usually with different coverage — which left 115
    colleges showing a different score depending on which code a caller used
    (gaps up to 25 pts). Score each college NAME over the UNION of its paired
    codes' subsets (best value per subset — the same rule get_college_profile
    displays) and write the same score/completeness to every paired code.
    Idempotent.
    """
    cur = conn.cursor()
    groups = cur.execute("""
        SELECT college_name, GROUP_CONCAT(college_code)
        FROM colleges GROUP BY college_name HAVING COUNT(*) > 1
    """).fetchall()
    synced = 0
    for name, codes_csv in groups:
        codes = codes_csv.split(",")
        ph = ",".join("?" * len(codes))
        rows = cur.execute(
            f"SELECT subset_name, MAX(score) FROM college_subset_scores "
            f"WHERE college_code IN ({ph}) GROUP BY subset_name", codes).fetchall()
        if not rows:
            continue
        score = round(sum(r[1] for r in rows) / len(rows) * 10, 1)
        completeness = round(len(rows) / TOTAL_SUBSETS * 100, 1)
        cur.execute(
            f"UPDATE colleges SET score=?, completeness=? WHERE college_code IN ({ph})",
            [score, completeness] + codes)
        synced += 1
    conn.commit()
    print(f"  Paired-code score sync: {synced} college name groups unified.")
    return synced


def print_summary(conn):
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM home_university_map")
    print(f"  home_university_map   : {cur.fetchone()[0]} districts")
    cur.execute("SELECT COUNT(*) FROM college_details")
    print(f"  college_details       : {cur.fetchone()[0]} profiles")
    cur.execute("SELECT COUNT(*) FROM college_subset_scores")
    print(f"  college_subset_scores : {cur.fetchone()[0]} scores")
    cur.execute("SELECT COUNT(*) FROM predictions_2026")
    print(f"  predictions_2026      : {cur.fetchone()[0]} predictions")
    cur.execute("SELECT COUNT(*) FROM subset_definitions")
    print(f"  subset_definitions    : {cur.fetchone()[0]} subsets")
    cur.execute("SELECT COUNT(*) FROM college_data_sources")
    print(f"  college_data_sources  : {cur.fetchone()[0]} field provenance records")
    cur.execute("SELECT status, COUNT(*) FROM scrape_progress GROUP BY status ORDER BY status")
    rows = cur.fetchall()
    if rows:
        summary = ", ".join(f"{s}:{n}" for s, n in rows)
        print(f"  scrape_progress       : {summary}")


if __name__ == "__main__":
    if not os.path.exists(DB_PATH):
        print(f"ERROR: {DB_PATH} not found. Run load_db.py first.")
        exit(1)

    conn = sqlite3.connect(DB_PATH)
    print("Setting up college profile tables...")
    setup(conn)
    sync_paired_code_scores(conn)
    print("\nCurrent table counts:")
    print_summary(conn)
    conn.close()
    print("\nDone. Run generate_predictions.py next to build 2026 cutoff predictions.")
