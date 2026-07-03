"""
scrape_all_colleges.py
Phase 3 — Automated web scraping for all 401 MHT CET CAP colleges.

Data sources (in order of priority):
  1. Wikipedia API          — year_established, campus_area_acres, website_url, type
  2. Official college site  — NAAC grade, NBA, hostel, autonomous, placements, fees
  (Shiksha.com / CollegeDunia were considered but block automated access via Akamai WAF)

Per-field source priority — higher priority is NEVER overwritten by lower:
  nirf_portal=5, naac_portal=5, official_website=4, wikipedia=3, shiksha=2

Data tagged is_official per source so counselors see provenance.
Checkpoint: scrape_progress table lets runs resume after interruption.

Usage:
  python scripts/scrape_all_colleges.py              # scrape all pending
  python scripts/scrape_all_colleges.py --limit 5    # test on first 5
  python scripts/scrape_all_colleges.py --code 06006 # single college
  python scripts/scrape_all_colleges.py --reset      # re-queue all as pending
  python scripts/scrape_all_colleges.py --summary    # show progress stats only
"""

import sqlite3
import sys
import os
import re
import time
import json
import datetime
import urllib.parse

DB_PATH = "db/edupath.db"
RATE_LIMIT = 1.5   # seconds between HTTP requests — polite scraping

SOURCE_PRIORITY = {
    "nirf_portal":      5,
    "naac_portal":      5,
    "official_website": 4,
    "wikipedia":        3,
    "shiksha":          2,
    "collegedunia":     2,
}

# Allowlist for college_details columns we write via f-string UPDATE (prevents SQL injection)
ALLOWED_FIELDS = {
    "naac_grade", "naac_score", "nirf_rank", "nba_branches", "is_autonomous",
    "year_established", "institution_type", "management_name",
    "annual_fee_min", "annual_fee_max", "tfws_available",
    "campus_area_acres", "has_hostel_boys", "has_hostel_girls", "has_sports", "has_wifi",
    "placement_pct", "avg_package_lpa", "highest_package_lpa", "top_recruiters",
    "placement_source", "address", "website_url", "principal_name", "notes",
}

# ---------------------------------------------------------------------------
# HTTP helper
# ---------------------------------------------------------------------------

def _get(url, timeout=20, retries=2, extra_headers=None, verify_ssl=True):
    """
    GET with browser-like UA. Returns Response or None.
    Falls back to verify_ssl=False if SSL handshake fails — common for Indian college sites
    with expired or mismatched certificates.
    """
    try:
        import requests as req
        import urllib3
    except ImportError:
        print("ERROR: 'requests' not installed. Run: pip install requests beautifulsoup4")
        sys.exit(1)

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-IN,en;q=0.5",
    }
    if extra_headers:
        headers.update(extra_headers)

    for attempt in range(retries + 1):
        try:
            r = req.get(url, headers=headers, timeout=timeout,
                        allow_redirects=True, verify=verify_ssl)
            return r
        except req.exceptions.SSLError:
            if verify_ssl:
                # Retry without SSL verification — many Indian college sites have cert issues
                urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
                try:
                    r = req.get(url, headers=headers, timeout=timeout,
                                allow_redirects=True, verify=False)
                    return r
                except Exception:
                    pass
            return None
        except Exception:
            if attempt < retries:
                time.sleep(1)
    return None


# ---------------------------------------------------------------------------
# Wikipedia API
# ---------------------------------------------------------------------------

WIKI_UA = "EduPathBot/1.0 (educational research; non-commercial; contact edupathmhtcet@gmail.com)"

def _wiki_api(params):
    """Call Wikipedia API. Returns parsed JSON or {}."""
    base = "https://en.wikipedia.org/w/api.php"
    params.update({"format": "json", "origin": "*"})
    r = _get(base + "?" + urllib.parse.urlencode(params),
             timeout=15, extra_headers={"User-Agent": WIKI_UA})
    if r and r.status_code == 200:
        try:
            return r.json()
        except Exception:
            pass
    return {}


def search_wikipedia(college_name, city):
    """
    Search Wikipedia for a college page.
    Returns (page_title, wiki_url) or (None, None).
    Matches on title OR snippet text (catches abbreviations like COEP).
    """
    clean = re.sub(r"\s+(pvt\.?|ltd\.?|trust|society|mandal|samiti|sanstha)\s*$", "",
                   college_name, flags=re.IGNORECASE).strip()

    for query in [f"{clean} {city} Maharashtra", f"{clean} engineering Maharashtra"]:
        data = _wiki_api({
            "action": "query", "list": "search",
            "srsearch": query, "srlimit": 5,
            "srnamespace": "0",
            "srprop": "title",
        })
        results = data.get("query", {}).get("search", [])
        for hit in results:
            title = hit.get("title", "")
            # Match on title only — snippets can quote the college name inside
            # university/list pages (e.g. SGBAU listing Rajendra Gode IT as an
            # affiliate), giving Jaccard=1.0 on the snippet even though the page
            # is about a completely different institution.
            if _name_matches(college_name, title):
                return title, f"https://en.wikipedia.org/wiki/{urllib.parse.quote(title)}"
        if results:
            time.sleep(0.3)

    return None, None


def _name_matches(db_name, text):
    """
    Fuzzy check: does `text` refer to the same college as db_name?

    Design decisions (each driven by a class of observed false positives):

    STOP set includes trust/org suffixes (shikshan, sanstha, prasarak, mandal…)
    and generic qualifiers (government, national, vidyapeeth…) that appear in
    hundreds of college names and Wikipedia articles — they carry zero signal.
    "college" and "institute" are NOT in STOP: they're discriminators (e.g.
    "G.H. Raisoni College of Engineering" vs "G.H. Raisoni Institute of
    Engineering" are two different campuses — stripping both would conflate them).

    City-conflict guard: if the college is in city A and Wikipedia title/snippet
    puts the institution in city B, reject immediately.  Catches "GCE Ratnagiri"
    matching "Government College of Engineering, Karad" which have identical
    distinctive words.

    Jaccard threshold 0.50 (strictly greater than): parent-university pages
    (Bharati Vidyapeeth, SPPU, BAMU, NMU) share only 1-2 words with affiliated
    engineering colleges — Jaccard ends up at ~0.20-0.33, well below 0.50.

    No long_common fallback: the old fallback fired when Wikipedia snippets
    quoted the search query verbatim (e.g. SGBAU's Wikipedia snippet mentions
    "Dr. Rajendra Gode Institute of Technology" as an affiliated college →
    "rajendra" and "gode" appear in both sets → false match).
    """
    # Generic words excluded from distinctive matching.
    # NOTE: "college" and "institute" intentionally omitted — they act as
    # discriminators between same-trust campuses (College vs Institute).
    STOP = {
        # Articles / prepositions
        "of", "and", "the", "a", "an", "in", "at", "for", "&", "s",
        # Trust / org suffixes — every trust-run college has these; zero signal
        "sanstha", "shikshan", "mandal", "trust", "society", "foundation",
        "prasarak", "pratishthan", "vikas", "samaj", "sangh", "charitable",
        "samstha", "stree", "rayat", "charities",
        # Honorifics / salutations before person names
        "shri", "shree", "smt", "prof", "late",
        # Generic geographic qualifiers
        "india", "maharashtra",
        # Very generic education-type terms that appear in thousands of articles
        "university", "engineering", "technology", "sciences", "management",
        "technical", "educational", "education",
        # "Vidyapeeth" = seat of learning in Sanskrit; used in many trust names
        "vidyapeeth",
        # "Government" and "national" appear in every govt college name and in
        # Wikipedia snippets about any government institution
        "government", "govt", "national",
    }

    EDU_WORDS = {"college", "institute", "university", "engineering", "technology",
                 "polytechnic", "school", "academy", "sciences", "technical",
                 "educational", "institutions"}

    # Maharashtra districts, cities, and neighbourhoods that appear in college names
    CITY = {
        "pune", "mumbai", "nagpur", "nashik", "aurangabad", "kolhapur", "solapur",
        "amravati", "thane", "sangli", "satara", "akola", "nanded", "jalgaon",
        "latur", "buldhana", "ahmednagar", "nandurbar", "dhule", "wardha",
        "chandrapur", "yavatmal", "washim", "beed", "osmanabad", "dharashiv",
        "parbhani", "hingoli", "gondia", "bhandara", "gadchiroli", "raigad",
        "ratnagiri", "sindhudurg", "palghar", "matunga", "dadar", "wadala",
        "andheri", "borivali", "mulund", "dombivli", "kalyan", "navi",
        # Smaller towns / suburbs that appear in college names
        "vasai", "virar", "mira", "bhayandar", "badlapur", "ambernath",
        "ulhasnagar", "bhiwandi", "panvel", "khopoli", "badner", "sevagram",
        "butibori", "hingna", "alandi", "khed", "lohegaon", "chakan",
        "baramati", "islampur", "ichalkaranji", "miraj", "karad", "wai",
        "phaltan", "kolhapur", "bhor", "talegaon", "wagholi",
        "jalna", "paithan", "ambajogai", "udgir", "nilanga",
        "nandurbar", "shahada", "malegaon", "bhusawal",
    }

    text_lower = text.lower()

    # Step 1: reject pages that have no educational-institution keywords at all
    if not any(w in text_lower for w in EDU_WORDS):
        return False

    def words(s):
        return {w.lower() for w in re.findall(r'\w+', s)
                if w.lower() not in STOP and len(w) > 2}

    a = words(db_name)
    b = words(text)
    if not a or not b:
        return False

    a_city = {w for w in a if w in CITY}
    b_city = {w for w in b if w in CITY}
    a_dist = a - CITY   # distinctive (non-city) words from college name
    b_dist = b - CITY   # distinctive (non-city) words from text

    # Step 2: city-conflict guard — different explicit cities → reject immediately.
    # Handles "GCE Ratnagiri" vs "GCE Karad", "GCE Aurangabad" vs COEP Pune, etc.
    if a_city and b_city and not (a_city & b_city):
        return False

    # Step 3: both have distinctive words → require Jaccard > 0.50
    if a_dist and b_dist:
        inter = len(a_dist & b_dist)
        union = len(a_dist | b_dist)
        return (inter / union) >= 0.50

    # Step 4: both have ONLY city words → same city required
    if not a_dist and not b_dist:
        return bool(a_city & b_city)

    # Step 5: one side has distinctive words, other only city → not the same college
    return False


def scrape_wikipedia(wiki_title):
    """
    Extract college profile data from a Wikipedia infobox.
    Returns dict of field->value.
    """
    data = _wiki_api({
        "action": "query", "titles": wiki_title,
        "prop": "revisions", "rvprop": "content",
        "rvslots": "main",
    })
    pages = data.get("query", {}).get("pages", {})
    wikitext = ""
    for page in pages.values():
        revs = page.get("revisions", [])
        if revs:
            wikitext = revs[0].get("slots", {}).get("main", {}).get("*", "")
            break

    if not wikitext:
        return {}

    result = {}

    # --- Year established ---
    # Handle: | established = 1887
    #         | established = {{Start date|1887|df=yes}}
    #         | former_names = 1854–1864: ...  (year in former_names for renamed colleges)
    for yr_pat in [
        r'\|\s*established\s*=\s*(?:\{\{[Ss]tart\s*[Dd]ate[^|]*\|)?(\d{4})',
        r'\|\s*founded\s*=\s*(?:\{\{[Ss]tart\s*[Dd]ate[^|]*\|)?(\d{4})',
        r'[Ee]stablished\s+in\s+(\d{4})',
        r'[Ff]ounded\s+in\s+(\d{4})',
    ]:
        yr_m = re.search(yr_pat, wikitext, re.IGNORECASE)
        if yr_m:
            yr = int(yr_m.group(1))
            if 1800 <= yr <= 2025:
                result["year_established"] = yr
                break

    # --- Campus area ---
    # Handle: campus = {{convert|51|acre|...}} or campus = 25 acres or campus = 25 ha
    campus_m = re.search(
        r'\|\s*campus\s*=\s*(?:\{\{[Cc]onvert\|)?([\d.]+)\|?\s*(?:acre|ha)',
        wikitext, re.IGNORECASE
    )
    if campus_m:
        try:
            val = float(campus_m.group(1))
            # If unit is ha, convert to acres (1 ha = 2.47 acres)
            unit_check = wikitext[campus_m.start():campus_m.end()+5]
            if 'ha' in unit_check and 'acre' not in unit_check:
                val = round(val * 2.471, 1)
            if 0.5 <= val <= 10000:
                result["campus_area_acres"] = val
        except ValueError:
            pass

    # --- Website ---
    # Handle: website = {{URL|https://...}} or website = https://...
    web_m = re.search(
        r'\|\s*website\s*=\s*(?:\{\{[Uu][Rr][Ll]\|)?([Hh]ttps?://[^\s\|\}\]\n]+)',
        wikitext
    )
    if web_m:
        url = web_m.group(1).strip().rstrip("}|/").rstrip("/")
        if url.startswith("http"):
            result["website_url"] = url

    # --- Institution type ---
    type_m = re.search(r'\|\s*type\s*=\s*([^\|\n\{]+)', wikitext, re.IGNORECASE)
    if type_m:
        raw_type = type_m.group(1).lower()
        if any(w in raw_type for w in ["government", "public", "autonomous"]):
            result["institution_type"] = "gov"
        elif "aided" in raw_type:
            result["institution_type"] = "aided"
        elif "private" in raw_type:
            result["institution_type"] = "pvt"

    # --- NAAC grade (sometimes in infobox) ---
    naac_m = re.search(r'NAAC\s+(?:Grade|grade)?\s*[:\|=]?\s*([A-C][+]{0,2})', wikitext)
    if naac_m:
        grade = naac_m.group(1).upper()
        if grade in ("A++", "A+", "A", "B++", "B+", "B", "C"):
            result["naac_grade"] = grade

    return result


# ---------------------------------------------------------------------------
# Official college website scraper
# ---------------------------------------------------------------------------

def scrape_official_website(url):
    """
    Scrape an official college website for profile fields.
    Only high-confidence extractions — official sites display NAAC/NBA prominently.
    """
    try:
        from bs4 import BeautifulSoup
    except ImportError:
        return {}

    r = _get(url, timeout=20)
    if not r or r.status_code != 200:
        return {}

    try:
        soup = BeautifulSoup(r.text, "html.parser")
    except Exception:
        return {}

    # Remove script/style noise
    for tag in soup(["script", "style"]):
        tag.decompose()

    text = soup.get_text(separator=" ", strip=True)
    result = {}

    # --- NAAC grade ---
    naac_m = re.search(
        r'NAAC\s+(?:Grade|Accredited(?:\s+with\s+Grade)?|Rating|Graded|Reaccredited(?:\s+with)?|Assessed\s+with\s+Grade)?\s*[:\-–\s]?\s*["\']?([A-C][+]{0,2})["\']?',
        text, re.IGNORECASE
    )
    if not naac_m:
        # Also match "Grade A+" or "Accredited 'A'" patterns
        naac_m = re.search(r'(?:Grade|Grade\s+Point)\s+([A-C][+]{0,2})\s+(?:by\s+NAAC|from\s+NAAC|NAAC)', text, re.IGNORECASE)
    if naac_m:
        grade = naac_m.group(1).upper().strip()
        if grade in ("A++", "A+", "A", "B++", "B+", "B", "C"):
            result["naac_grade"] = grade

    # --- NAAC score ---
    naac_score_m = re.search(
        r'NAAC\s+(?:[Ss]core|[Gg]rade\s+[Pp]oint|[Cc]umulative\s+[Gg]rade\s+[Pp]oint\s+[Aa]verage|CGPA)\s*[:\-–]?\s*(\d\.\d+)\s*(?:/\s*4)?',
        text, re.IGNORECASE
    )
    if naac_score_m:
        try:
            sc = float(naac_score_m.group(1))
            if 0 < sc <= 4.0:
                result["naac_score"] = sc
        except ValueError:
            pass

    # --- NBA ---
    if re.search(r'NBA\s+[Aa]ccredited|[Aa]ccredited\s+by\s+NBA', text, re.IGNORECASE):
        result["nba_branches"] = result.get("nba_branches", "Yes")

    # --- Autonomous ---
    if re.search(
        r'[Aa]utonomous\s+(?:[Cc]ollege|[Ii]nstitute)|[Ss]tatus\s*[:\-–]\s*[Aa]utonomous',
        text
    ):
        result["is_autonomous"] = 1

    # --- Year established ---
    yr_m = re.search(
        r'(?:Established|Founded|Est\.?)\s*(?:in|:)?\s*(1[89]\d\d|20[012]\d)',
        text, re.IGNORECASE
    )
    if yr_m:
        yr = int(yr_m.group(1))
        if 1800 <= yr <= 2025:
            result["year_established"] = yr

    # --- Hostel ---
    tl = text.lower()
    if re.search(r'(?:boys?|male|gents?)\s+hostel', tl):
        result["has_hostel_boys"] = 1
    if re.search(r'(?:girls?|female|ladies?|women)\s+hostel', tl):
        result["has_hostel_girls"] = 1
    if re.search(r'hostel\s+(?:for\s+)?(?:both|all\s+students)', tl):
        result["has_hostel_boys"] = 1
        result["has_hostel_girls"] = 1

    # --- Campus area ---
    campus_m = re.search(
        r'(?:[Cc]ampus)?\s*(?:[Aa]rea|[Ss]pread)\s*[:\-–]?\s*([\d.]+)\s*[Aa]cres?', text
    )
    if not campus_m:
        campus_m = re.search(r'([\d.]+)\s*[Aa]cres?\s+(?:of\s+)?(?:campus|land|area)', text)
    if campus_m:
        try:
            acres = float(campus_m.group(1))
            if 0.5 <= acres <= 5000:
                result["campus_area_acres"] = acres
        except ValueError:
            pass

    # --- Sports ---
    if re.search(r'sports?\s+(?:complex|ground|facility|facilities|centre|stadium)', tl):
        result["has_sports"] = 1

    # --- WiFi ---
    if re.search(r'(?:wi-?fi|wireless\s+internet|smart\s+class(?:room)?)', tl):
        result["has_wifi"] = 1

    # --- Placement % (colleges self-report) ---
    plc_m = re.search(
        r'(\d{1,3}(?:\.\d)?)\s*%\s*(?:students?\s+)?[Pp]lace(?:d|ment)',
        text
    )
    if plc_m:
        pct = float(plc_m.group(1))
        if 0 < pct <= 100:
            result["placement_pct"] = pct
            result["placement_source"] = "college_website"

    # --- Average package ---
    avg_m = re.search(
        r'(?:Average|Avg\.?)\s+(?:Package|Salary|CTC)\s*[:\-–]?\s*(?:₹|INR|Rs\.?)?\s*([\d.]+)\s*(?:LPA|L)',
        text, re.IGNORECASE
    )
    if avg_m:
        try:
            val = float(avg_m.group(1))
            if 1 <= val <= 100:
                result["avg_package_lpa"] = val
        except ValueError:
            pass

    # --- Highest package ---
    high_m = re.search(
        r'(?:Highest|Maximum|Max\.?)\s+(?:Package|Salary|CTC)\s*[:\-–]?\s*(?:₹|INR|Rs\.?)?\s*([\d.]+)\s*(?:LPA|L)',
        text, re.IGNORECASE
    )
    if high_m:
        try:
            val = float(high_m.group(1))
            if 1 <= val <= 2000:
                result["highest_package_lpa"] = val
        except ValueError:
            pass

    # --- Annual fee ---
    fee_m = re.search(
        r'(?:Annual|Total|Tuition)\s+[Ff]ee[s]?\s*[:\-–]?\s*(?:₹|INR|Rs\.?)?\s*([\d,]+)',
        text
    )
    if fee_m:
        try:
            fee = float(fee_m.group(1).replace(",", ""))
            if 10_000 <= fee <= 20_00_000:
                result["annual_fee_min"] = fee
        except ValueError:
            pass

    return result


# ---------------------------------------------------------------------------
# DB write with source priority
# ---------------------------------------------------------------------------

def write_with_source(conn, code, fields, source_type, url, is_official):
    """
    Write fields to college_details (respecting source priority) and
    record provenance in college_data_sources.
    Returns count of fields actually written.
    """
    if not fields:
        return 0

    cur = conn.cursor()
    now = datetime.datetime.now().isoformat(timespec="seconds")
    my_priority = SOURCE_PRIORITY.get(source_type, 1)
    written = 0

    cur.execute("INSERT OR IGNORE INTO college_details (college_code) VALUES (?)", (code,))

    for field, value in fields.items():
        if value is None:
            continue
        if field not in ALLOWED_FIELDS:
            continue

        # Don't overwrite higher-priority source
        cur.execute(
            "SELECT source_type FROM college_data_sources WHERE college_code = ? AND field_name = ?",
            (code, field)
        )
        existing = cur.fetchone()
        if existing and SOURCE_PRIORITY.get(existing[0], 1) > my_priority:
            continue

        try:
            cur.execute(
                f"UPDATE college_details SET {field} = ?, last_updated = ? WHERE college_code = ?",
                (value, now, code)
            )
        except Exception as e:
            print(f"    WARN: could not write {field}: {e}")
            continue

        cur.execute("""
            INSERT INTO college_data_sources
                (college_code, field_name, source_type, source_url, is_official, retrieved_date)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(college_code, field_name) DO UPDATE SET
                source_type    = excluded.source_type,
                source_url     = excluded.source_url,
                is_official    = excluded.is_official,
                retrieved_date = excluded.retrieved_date
        """, (code, field, source_type, url, 1 if is_official else 0, now))

        written += 1

    return written


# ---------------------------------------------------------------------------
# scrape_progress initialization (deduplicated to 401 canonical colleges)
# ---------------------------------------------------------------------------

def _init_scrape_progress(conn):
    """
    Ensure scrape_progress has exactly the 401 canonical colleges.
    Canonical code = MAX(college_code) per college_name (matches college_details).
    Removes stale non-canonical rows inserted by earlier buggy runs.
    """
    cur = conn.cursor()

    # Step 1: Remove any rows whose code is NOT the canonical (max) code for that name
    cur.execute("""
        DELETE FROM scrape_progress
        WHERE college_code NOT IN (
            SELECT MAX(college_code) FROM colleges GROUP BY college_name
        )
    """)
    removed = cur.rowcount
    if removed > 0:
        print(f"  Cleaned {removed} non-canonical rows from scrape_progress.")

    # Step 2: Insert missing canonical entries
    cur.execute("""
        INSERT OR IGNORE INTO scrape_progress (college_code, college_name, status)
        SELECT MAX(c.college_code), c.college_name, 'pending'
        FROM colleges c
        GROUP BY c.college_name
    """)
    conn.commit()


# ---------------------------------------------------------------------------
# Per-college orchestration
# ---------------------------------------------------------------------------

def process_one(conn, code, name, city):
    """
    Scrape one college from Wikipedia + official site.
    Updates scrape_progress. Returns total fields written.
    """
    cur = conn.cursor()
    now = datetime.datetime.now().isoformat(timespec="seconds")
    fields_written = 0

    cur.execute(
        "UPDATE scrape_progress SET status = 'in_progress', last_attempted = ? WHERE college_code = ?",
        (now, code)
    )
    conn.commit()

    # Fetch current progress row
    cur.execute(
        "SELECT wikipedia_url, wikipedia_scraped, official_scraped FROM scrape_progress WHERE college_code = ?",
        (code,)
    )
    sp = cur.fetchone()
    wikipedia_url     = sp[0] if sp else None
    wiki_done         = bool(sp[1]) if sp else False
    official_done     = bool(sp[2]) if sp else False

    # Fetch website_url from college_details
    cur.execute("SELECT website_url FROM college_details WHERE college_code = ?", (code,))
    det = cur.fetchone()
    website_url = det[0] if det else None

    # ---- Phase 1: Wikipedia ----
    if not wiki_done:
        if not wikipedia_url:
            print(f"    Wikipedia search: {name[:55]}", end=" ... ", flush=True)
            wiki_title, wikipedia_url = search_wikipedia(name, city or "")
            if wikipedia_url:
                cur.execute(
                    "UPDATE scrape_progress SET wikipedia_url = ? WHERE college_code = ?",
                    (wikipedia_url, code)
                )
                conn.commit()
                print(f"found: {wiki_title}")
            else:
                print("not found")
            time.sleep(RATE_LIMIT)

        if wikipedia_url:
            # Extract title from URL for API call
            wiki_title = urllib.parse.unquote(wikipedia_url.split("/wiki/")[-1])
            print(f"    Wikipedia scrape: {wiki_title[:55]}", end=" ... ", flush=True)
            data = scrape_wikipedia(wiki_title)
            if data:
                # Website URL from Wikipedia → also use for official site scraping
                if "website_url" in data and not website_url:
                    website_url = data["website_url"]
                n = write_with_source(conn, code, data, "wikipedia", wikipedia_url, is_official=False)
                print(f"{n} fields  {list(data.keys())}")
                fields_written += n
            else:
                print("nothing")
            cur.execute(
                "UPDATE scrape_progress SET wikipedia_scraped = 1 WHERE college_code = ?", (code,)
            )
            conn.commit()
            time.sleep(RATE_LIMIT)

    # ---- Phase 2: Official website ----
    if not official_done:
        # Re-read website_url (might have been written by Wikipedia phase)
        if not website_url:
            cur.execute("SELECT website_url FROM college_details WHERE college_code = ?", (code,))
            det2 = cur.fetchone()
            website_url = det2[0] if det2 else None

        if website_url:
            print(f"    Official site: {website_url[:70]}", end=" ... ", flush=True)
            data = scrape_official_website(website_url)
            if data:
                n = write_with_source(conn, code, data, "official_website", website_url, is_official=True)
                print(f"{n} fields  {list(data.keys())}")
                fields_written += n
            else:
                print("nothing extracted")
            cur.execute(
                "UPDATE scrape_progress SET official_scraped = 1 WHERE college_code = ?", (code,)
            )
            conn.commit()
            time.sleep(RATE_LIMIT)
        else:
            print(f"    Official site: no URL available")

    # Recompute subset scores for this college
    try:
        from score_colleges import compute_scores_for_college
        compute_scores_for_college(conn, code)
        conn.commit()
    except Exception as e:
        print(f"    WARN: score recompute: {e}")

    status = "done" if fields_written > 0 else "failed"
    cur.execute(
        "UPDATE scrape_progress SET status = ?, last_attempted = ? WHERE college_code = ?",
        (status, now, code)
    )
    conn.commit()
    return fields_written


# ---------------------------------------------------------------------------
# Progress summary
# ---------------------------------------------------------------------------

def print_progress(conn):
    cur = conn.cursor()
    cur.execute("SELECT status, COUNT(*) FROM scrape_progress GROUP BY status ORDER BY status")
    rows = cur.fetchall()
    total = sum(n for _, n in rows)
    print(f"\n  Scrape progress ({total} colleges):")
    for status, n in rows:
        print(f"    {status:<14}: {n:>4}")

    cur.execute("""
        SELECT f.field_name, COUNT(*) as cnt, SUM(f.is_official) as off_cnt
        FROM college_data_sources f
        GROUP BY f.field_name
        ORDER BY cnt DESC
        LIMIT 20
    """)
    rows = cur.fetchall()
    if rows:
        print(f"\n  Fields scraped (out of 401 colleges):")
        for field, cnt, off in rows:
            tag = "(official)" if off and off > cnt * 0.5 else "(aggregator)"
            print(f"    {field:<24}: {cnt:>4}  {tag}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    args = sys.argv[1:]
    reset       = "--reset" in args
    summary_only = "--summary" in args
    single_code = None
    limit       = None

    if "--code" in args:
        idx = args.index("--code")
        if idx + 1 < len(args):
            single_code = args[idx + 1]

    if "--limit" in args:
        idx = args.index("--limit")
        if idx + 1 < len(args):
            try:
                limit = int(args[idx + 1])
            except ValueError:
                print("ERROR: --limit requires an integer")
                sys.exit(1)

    if not os.path.exists(DB_PATH):
        print(f"ERROR: {DB_PATH} not found. Run load_db.py first.")
        sys.exit(1)

    conn = sqlite3.connect(DB_PATH)

    # Check required tables exist
    cur = conn.cursor()
    for tbl in ("college_data_sources", "scrape_progress"):
        cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (tbl,))
        if not cur.fetchone():
            print(f"ERROR: table '{tbl}' missing. Run: python scripts/setup_college_profiles.py")
            conn.close()
            sys.exit(1)

    # Dedup scrape_progress to 401 canonical colleges
    _init_scrape_progress(conn)

    # Reset stale in_progress (interrupted previous runs) to pending
    conn.execute(
        "UPDATE scrape_progress SET status = 'pending' WHERE status = 'in_progress'"
    )
    conn.commit()

    if reset:
        conn.execute(
            "UPDATE scrape_progress SET status = 'pending', "
            "wikipedia_scraped = 0, official_scraped = 0, last_attempted = NULL"
        )
        conn.commit()
        print("All scrape_progress entries reset to pending.")

    if summary_only:
        print_progress(conn)
        conn.close()
        return

    # Select colleges to process
    if single_code:
        cur.execute("""
            SELECT sp.college_code, sp.college_name, c.city
            FROM scrape_progress sp
            LEFT JOIN colleges c ON c.college_code = sp.college_code
            WHERE sp.college_code = ?
        """, (single_code,))
    else:
        cur.execute("""
            SELECT sp.college_code, sp.college_name, c.city
            FROM scrape_progress sp
            LEFT JOIN colleges c ON c.college_code = sp.college_code
            WHERE sp.status IN ('pending', 'failed')
            ORDER BY sp.college_code
        """)

    colleges = cur.fetchall()
    if limit:
        colleges = colleges[:limit]

    if not colleges:
        print("No pending colleges. Use --reset to re-queue, or --summary for stats.")
        print_progress(conn)
        conn.close()
        return

    print(f"\nEduPath College Scraper — {len(colleges)} colleges to process")
    print(f"Sources: Wikipedia API + official college websites")
    print(f"Rate limit: {RATE_LIMIT}s between requests\n")

    total_fields = 0
    done_count   = 0

    for i, (code, name, city) in enumerate(colleges, 1):
        print(f"\n[{i}/{len(colleges)}] {name[:60]} | {city or '?'} | {code}")
        try:
            n = process_one(conn, code, name, city or "")
            total_fields += n
            if n > 0:
                done_count += 1
        except KeyboardInterrupt:
            print("\n\nInterrupted. Progress saved — run again to resume.")
            break
        except Exception as e:
            print(f"    ERROR: {e}")
            conn.execute(
                "UPDATE scrape_progress SET status = 'failed', last_attempted = ? WHERE college_code = ?",
                (datetime.datetime.now().isoformat(timespec="seconds"), code)
            )
            conn.commit()

        # Periodic score recompute every 25 colleges
        if i % 25 == 0:
            try:
                from setup_college_profiles import compute_college_scores
                compute_college_scores(conn)
                conn.commit()
                print(f"\n  [checkpoint] Recomputed overall scores after {i} colleges.")
            except Exception as e:
                print(f"  [checkpoint] Score recompute error: {e}")
            print_progress(conn)

    # Final score recompute
    try:
        from setup_college_profiles import compute_college_scores
        compute_college_scores(conn)
        conn.commit()
    except Exception as e:
        print(f"Final score recompute error: {e}")

    print(f"\n{'='*65}")
    print(f"Scraping complete.")
    print(f"  Colleges processed : {len(colleges)}")
    print(f"  With new data      : {done_count}")
    print(f"  Total fields saved : {total_fields}")
    print_progress(conn)
    conn.close()
    print("\nNext: python -m unittest discover -s tests")


if __name__ == "__main__":
    main()
