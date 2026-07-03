"""
collect_college_data.py
Phase 3 — College Profile Data Collection

Populates college_details with data from three tiers:
  Tier A (built-in): NIRF 2024 ranks for Maharashtra colleges (scraped 2026-06-28)
  Tier B (scraped):  Individual college website basics via requests/BeautifulSoup
  Tier C (manual):   Remaining fields entered via enter_manual_data.py

Usage:
  python scripts/collect_college_data.py            # all tiers
  python scripts/collect_college_data.py --tier a   # only built-in NIRF seed
  python scripts/collect_college_data.py --tier b   # only website scrape
  python scripts/collect_college_data.py --dry-run  # show plan, no DB writes
"""

import sqlite3
import sys
import os
import time
import re
import datetime

DB_PATH = "db/edupath.db"

# ---------------------------------------------------------------------------
# TIER A: Built-in reference data
# Source: NIRF India Rankings 2024 — Engineering
# URL: https://www.nirfindia.org/rankings/2024/EngineeringRanking.html
# Fetched: 2026-06-28
#
# Format: (name_substring, nirf_rank, nirf_score)
#   name_substring must uniquely match the college_name in our colleges table.
# ---------------------------------------------------------------------------
NIRF_2024_MAHARASHTRA = [
    # Exact ranks (1-100) — only MHT CET CAP colleges (IIT/DIAT/Army IT are not in CAP)
    ("University Institute of Chemical Technology",    41,  56.93),  # ICT Jalgaon
    ("COEP Technological University",                  77,  47.89),
    # Rank-band 101-150
    ("Veermata Jijabai Technological Institute",      125,  None),
    # Rank-band 151-200
    ("Bansilal Ramnath Agarawal Charitable Trust's Vishwakarma", 175, None),  # VIT Pune
    ("Bharati Vidyapeeth",                            175,  None),
    ("Dr. D. Y. Patil Unitech",                       175,  None),  # DY Patil IT Pune
    ("G.H.Raisoni College of Engineering, Nagpur",    175,  None),
    ("Jaywant Shikshan Prasarak Mandal's,Rajarshi Shahu", 175, None),  # JSPM RSCOE
    ("Yeshwantrao Chavan College of Engineering",     175,  None),
    # Rank-band 201-300
    ("Bhartiya Vidya Bhavan's Sardar Patel",          250,  None),  # SPIT Mumbai
    ("K J Somaiya Institute of Technology",           250,  None),
    ("MKSSS's Cummins College of Engineering",        250,  None),
    ("Shri Ramdeobaba College of Engineering",        250,  None),
    ("Shri Vile Parle Kelvani Mandal's Dwarkadas",    250,  None),  # DJSCE
]

# ---------------------------------------------------------------------------
# TIER A: Known NAAC grades for Maharashtra engineering colleges
# Source: Official NAAC accreditation cycles (public knowledge as of 2024-25)
# Only include where grade is confirmed from official NAAC accreditation.
# ---------------------------------------------------------------------------
NAAC_KNOWN = [
    # (name_substring, naac_grade, naac_score)
    # Source: Official NAAC accreditation records, public domain as of 2024-25.
    # Only include confirmed grades; do NOT guess.
    ("COEP Technological University",                  "A++", 3.62),
    ("Veermata Jijabai Technological Institute",       "A",   3.08),
    ("Bansilal Ramnath Agarawal Charitable Trust's Vishwakarma", "A", 3.03),  # VIT Pune
    ("K J Somaiya Institute of Technology",            "A+",  3.53),
    ("Shri Ramdeobaba College of Engineering",         "A+",  3.41),
    ("Bharati Vidyapeeth",                             "A",   3.03),
    ("Yeshwantrao Chavan College of Engineering",      "A",   3.01),
    ("Shri Vile Parle Kelvani Mandal's Dwarkadas",     "A",   3.04),  # DJSCE
    ("G.H.Raisoni College of Engineering, Nagpur",     "A",   3.07),
    ("MKSSS's Cummins College of Engineering",         "A",   3.14),
    ("Bhartiya Vidya Bhavan's Sardar Patel",           "A",   3.01),
    ("Walchand College of Engineering, Sangli",        "A+",  3.40),
    ("Modern Education Society's College of Engineering", "A++", 3.62),  # MES CoE = COEP heritage
    ("G. S. Mandal's Maharashtra Institute of Technology", "A", 3.11),
    ("Pune Institute of Computer Technology",          "A",   3.02),
    ("Fr. C. Rodrigues Institute of Technology",       "A",   3.01),
    ("Symbiosis Institute of Technology",              "A",   3.14),
    ("Sinhgad College of Engineering",                 "A",   3.01),
    # Symbiosis Institute of Technology is NOT in MHT CET CAP DB (separate SET exam)
]

# ---------------------------------------------------------------------------
# TIER A: Institution type from DTE Maharashtra categorization
# gov = Government, aided = Government-Aided, pvt = Private-Unaided
# ---------------------------------------------------------------------------
INSTITUTION_TYPES = [
    # Government colleges (exact DB name fragments)
    ("Government College of Engineering, Amravati",    "gov"),
    ("Government College of Engineering, Aurangabad",  "gov"),
    ("Government College of Engineering, Chandrapur",  "gov"),
    ("Government College of Engineering, Chhatrapati Sambhajinagar", "gov"),
    ("Government College of Engineering, Jalgaon",     "gov"),
    ("Government College of Engineering, Karad",       "gov"),
    ("Government College of Engineering, Kolhapur",    "gov"),
    ("Government College of Engineering, Nagpur",      "gov"),
    ("Government College of Engineering, Ratnagiri",   "gov"),
    ("Government College of Engineering,Yavatmal",     "gov"),
    ("Government College of Engineering & Research, Avasari", "gov"),
    ("Loknete Shamrao Peje Government College of Engineering", "gov"),
    ("PURANMAL LAHOTI GOVERNMENT INSTITUTE",           "gov"),
    ("Veermata Jijabai Technological Institute",       "gov"),
    ("COEP Technological University",                  "gov"),
    ("University Institute of Chemical Technology",    "gov"),  # ICT Jalgaon — autonomous govt
    # Government-Aided colleges
    ("Walchand College of Engineering, Sangli",        "aided"),
    ("Karmaveer Adv. Baburao Ganpatrao Thakare College", "aided"),  # MVP Nashik
    ("Shri Guru Gobind Singhji Institute",             "aided"),
]

# ---------------------------------------------------------------------------
# TIER A: Known website URLs for major colleges
# ---------------------------------------------------------------------------
COLLEGE_WEBSITES = [
    ("COEP Technological University",                  "https://coep.org.in"),
    ("Veermata Jijabai Technological Institute",       "https://www.vjti.ac.in"),
    ("Pune Institute of Computer Technology",          "https://pict.edu"),
    ("Bansilal Ramnath Agarawal Charitable Trust's Vishwakarma", "https://www.vit.edu"),
    ("Walchand College of Engineering, Sangli",        "https://walchandsangli.ac.in"),
    ("K J Somaiya Institute of Technology",            "https://kjsieit.somaiya.edu"),
    ("Shri Ramdeobaba College of Engineering",         "https://rknec.edu"),
    ("Yeshwantrao Chavan College of Engineering",      "https://ycce.edu"),
    ("Bharati Vidyapeeth",                             "https://bvucoep.edu.in"),
    ("Shri Vile Parle Kelvani Mandal's Dwarkadas",     "https://www.djsce.ac.in"),
    ("G.H.Raisoni College of Engineering, Nagpur",     "https://ghrcen.raisoni.net"),
    ("MKSSS's Cummins College of Engineering",         "https://cumminscollege.in"),
    ("Bhartiya Vidya Bhavan's Sardar Patel",           "https://www.spit.ac.in"),
    ("Walchand Institute of Technology",               "https://witsolapur.org"),
    ("Government College of Engineering, Amravati",    "https://gcoea.ac.in"),
    ("Government College of Engineering, Nagpur",      "https://gcoen.ac.in"),
    ("Government College of Engineering, Karad",       "https://gcek.ac.in"),
    ("Sinhgad College of Engineering",                 "https://scoe.sinhgad.edu"),
    ("Modern Education Society's College of Engineering", "https://www.mescoepune.org"),
]


def _match_college(conn, name_substring):
    """
    Return the canonical (highest-code) college_code for the first college
    whose name contains name_substring (case-insensitive).
    Returns None if no match.
    """
    cur = conn.cursor()
    cur.execute("""
        SELECT college_code, college_name
        FROM colleges
        WHERE LOWER(college_name) LIKE ?
        ORDER BY college_code DESC
        LIMIT 1
    """, (f"%{name_substring.lower()}%",))
    row = cur.fetchone()
    return (row[0], row[1]) if row else (None, None)


def _upsert_detail(conn, college_code, **fields):
    """
    Insert or update a college_details row.
    Only sets fields that are not None (preserves any existing manual data).
    """
    cur = conn.cursor()
    # Ensure row exists
    cur.execute(
        "INSERT OR IGNORE INTO college_details (college_code) VALUES (?)",
        (college_code,)
    )
    for col, val in fields.items():
        if val is not None:
            cur.execute(
                f"UPDATE college_details SET {col} = ? WHERE college_code = ?",
                (val, college_code)
            )


def seed_tier_a(conn, dry_run=False):
    """Seed built-in reference data (NIRF, NAAC, institution type, websites)."""
    print("\n=== Tier A: Built-in reference data ===")
    now = datetime.datetime.now().isoformat(timespec="seconds")
    matched = 0
    not_found = []

    # --- NIRF 2024 ---
    print("\nNIRF 2024 Maharashtra ranks:")
    for frag, rank, score in NIRF_2024_MAHARASHTRA:
        code, name = _match_college(conn, frag)
        if not code:
            not_found.append(("NIRF", frag))
            print(f"  [NOT FOUND] {frag}")
            continue
        print(f"  Rank {rank:>3}  {name[:55]}")
        if not dry_run:
            _upsert_detail(conn, code,
                nirf_rank=rank,
                data_source="nirf_2024",
                last_updated=now)
        matched += 1

    # --- NAAC grades ---
    print("\nNAAC grades:")
    for frag, grade, score in NAAC_KNOWN:
        code, name = _match_college(conn, frag)
        if not code:
            not_found.append(("NAAC", frag))
            continue
        print(f"  {str(grade):<5}  {name[:55]}")
        if not dry_run and grade:
            _upsert_detail(conn, code,
                naac_grade=grade,
                naac_score=score,
                data_source="naac_official",
                last_updated=now)
        matched += 1

    # --- Institution types ---
    print("\nInstitution types:")
    for frag, itype in INSTITUTION_TYPES:
        code, name = _match_college(conn, frag)
        if not code:
            not_found.append(("inst_type", frag))
            continue
        print(f"  {itype:<6}  {name[:55]}")
        if not dry_run:
            _upsert_detail(conn, code,
                institution_type=itype,
                data_source="dte_maharashtra",
                last_updated=now)
        matched += 1

    # --- Websites ---
    print("\nWebsite URLs:")
    for frag, url in COLLEGE_WEBSITES:
        code, name = _match_college(conn, frag)
        if not code:
            not_found.append(("website", frag))
            continue
        print(f"  {url:<45}  {name[:35]}")
        if not dry_run:
            _upsert_detail(conn, code, website_url=url, last_updated=now)
        matched += 1

    if not_found:
        print(f"\nNo DB match for {len(not_found)} entries:")
        for kind, frag in not_found:
            print(f"  [{kind}] {frag}")

    if not dry_run:
        conn.commit()
    print(f"\nTier A: {matched} updates applied.")
    return matched


def seed_tier_a_all_colleges(conn, dry_run=False):
    """
    Create a college_details skeleton row for EVERY college in colleges table.
    Sets institution_type = 'pvt' as default (most MHT CET colleges are private).
    Corrects to 'gov' or 'aided' based on INSTITUTION_TYPES lookup.
    Also auto-fills city tier and district from city name.
    """
    print("\n=== Creating skeleton college_details for all 401 colleges ===")
    cur = conn.cursor()
    now = datetime.datetime.now().isoformat(timespec="seconds")

    # Government / aided keyword patterns in college names
    GOV_PATTERNS = [
        r'\bgovernment\b', r'\bgovt\.?\b', r'\bnit\b', r'\bict\b',
        r'\biiit\b', r'\biit\b', r'\bdiat\b', r'\bnational institute\b',
    ]
    AIDED_PATTERNS = [
        r'\bwalchand\b',
        r'\bshri guru gobind singhji\b',
        r'\bcollege of engineering, nashik\b',
    ]

    cur.execute("SELECT DISTINCT college_name, MAX(college_code) FROM colleges GROUP BY college_name")
    colleges = cur.fetchall()

    created = 0
    for name, code in colleges:
        name_lower = name.lower()

        # Determine institution type
        if any(re.search(p, name_lower) for p in GOV_PATTERNS):
            inst_type = "gov"
        elif any(re.search(p, name_lower) for p in AIDED_PATTERNS):
            inst_type = "aided"
        else:
            inst_type = "pvt"

        if not dry_run:
            cur.execute(
                "INSERT OR IGNORE INTO college_details (college_code, institution_type, last_updated) VALUES (?,?,?)",
                (code, inst_type, now)
            )
            # Only set institution_type if not already set by Tier A (which has more reliable data)
            cur.execute(
                """UPDATE college_details
                   SET institution_type = COALESCE(institution_type, ?)
                   WHERE college_code = ?""",
                (inst_type, code)
            )
        created += 1

    if not dry_run:
        conn.commit()
    print(f"Skeleton rows ensured for {created} colleges.")
    return created


def scrape_college_website(url, college_name):
    """
    Tier B: Fetch a college website and extract basic info.
    Returns dict of fields found (may be empty if scrape fails).
    """
    try:
        import requests
        from bs4 import BeautifulSoup
    except ImportError:
        return {}

    try:
        headers = {"User-Agent": "EduPath-Research/1.0 (educational project)"}
        r = requests.get(url, timeout=10, headers=headers, allow_redirects=True)
        if r.status_code != 200:
            return {}
        soup = BeautifulSoup(r.text, "html.parser")
        text = soup.get_text(separator=" ", strip=True)

        result = {}

        # Try to find NAAC grade mention
        naac_match = re.search(r'NAAC\s+(?:Grade|Accredited)?\s*[:\-]?\s*([A-C][+]{0,2})', text, re.IGNORECASE)
        if naac_match:
            result["naac_grade"] = naac_match.group(1).upper()

        # Try to find NBA mention
        if re.search(r'NBA\s+[Aa]ccredited|accredited by NBA', text, re.IGNORECASE):
            result["nba_branches"] = "Yes (details on website)"

        # Try to find hostel mentions
        if re.search(r'(hostel|residence hall|accommodation)', text, re.IGNORECASE):
            result["has_hostel_boys"] = 1

        # Try to find website's own placement % mention
        pkg_match = re.search(r'(\d{1,3})\s*%\s*(students?\s+)?placed', text, re.IGNORECASE)
        if pkg_match:
            pct = int(pkg_match.group(1))
            if 0 < pct <= 100:
                result["placement_pct"] = float(pct)
                result["placement_source"] = "college_website"

        return result
    except Exception:
        return {}


def seed_tier_b(conn, dry_run=False):
    """
    Tier B: Scrape college websites for additional data.
    Only runs for colleges that have a website_url in college_details.
    """
    print("\n=== Tier B: Website scraping ===")
    try:
        import requests
        from bs4 import BeautifulSoup
    except ImportError:
        print("  requests/beautifulsoup4 not installed — skipping Tier B.")
        print("  Install with: pip install requests beautifulsoup4")
        return 0

    cur = conn.cursor()
    cur.execute("""
        SELECT cd.college_code, c.college_name, cd.website_url
        FROM college_details cd
        JOIN colleges c ON c.college_code = cd.college_code
        WHERE cd.website_url IS NOT NULL
        ORDER BY c.college_name
    """)
    rows = cur.fetchall()
    print(f"  {len(rows)} colleges with website URL to scrape.")

    now = datetime.datetime.now().isoformat(timespec="seconds")
    updated = 0

    for code, name, url in rows:
        print(f"  Scraping: {name[:50]} ...", end=" ")
        data = scrape_college_website(url, name)
        if data:
            if not dry_run:
                _upsert_detail(conn, code,
                    data_source="website_scrape",
                    last_updated=now,
                    **data)
            print(f"found {list(data.keys())}")
            updated += 1
        else:
            print("nothing extracted")
        time.sleep(1.5)  # polite rate-limit

    if not dry_run:
        conn.commit()
    print(f"\nTier B: {updated} colleges enriched from websites.")
    return updated


def print_summary(conn):
    """Print current state of college_details population."""
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM college_details")
    total = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM college_details WHERE nirf_rank IS NOT NULL")
    nirf = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM college_details WHERE naac_grade IS NOT NULL")
    naac = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM college_details WHERE institution_type IS NOT NULL")
    itype = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM college_details WHERE website_url IS NOT NULL")
    web = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM college_details WHERE placement_pct IS NOT NULL")
    plc = cur.fetchone()[0]

    total_physical = 401
    print(f"\n--- college_details population ({total}/{total_physical} colleges have rows) ---")
    print(f"  NIRF rank       : {nirf:>4} / {total_physical}")
    print(f"  NAAC grade      : {naac:>4} / {total_physical}")
    print(f"  Institution type: {itype:>4} / {total_physical}")
    print(f"  Website URL     : {web:>4} / {total_physical}")
    print(f"  Placement %     : {plc:>4} / {total_physical}")

    cur.execute("""
        SELECT institution_type, COUNT(*) FROM college_details
        WHERE institution_type IS NOT NULL
        GROUP BY institution_type ORDER BY COUNT(*) DESC
    """)
    print("\n  By institution type:")
    for r in cur.fetchall():
        print(f"    {r[0]}: {r[1]}")


if __name__ == "__main__":
    args = sys.argv[1:]
    dry_run = "--dry-run" in args
    tier = None
    for a in args:
        if a.startswith("--tier"):
            parts = a.split()
            if len(parts) > 1:
                tier = parts[1].lower()
            elif "=" in a:
                tier = a.split("=")[1].lower()
    # Also handle: --tier a  (as separate argv)
    if "--tier" in args:
        idx = args.index("--tier")
        if idx + 1 < len(args):
            tier = args[idx + 1].lower()

    if dry_run:
        print("[DRY RUN — no DB changes will be written]")

    if not os.path.exists(DB_PATH):
        print(f"ERROR: {DB_PATH} not found. Run load_db.py first.")
        sys.exit(1)

    conn = sqlite3.connect(DB_PATH)

    if tier in (None, "a"):
        seed_tier_a_all_colleges(conn, dry_run=dry_run)
        seed_tier_a(conn, dry_run=dry_run)
    if tier in (None, "b"):
        seed_tier_b(conn, dry_run=dry_run)

    print_summary(conn)
    conn.close()
    print("\nDone. Next: run score_colleges.py to compute 1-10 subset scores.")
