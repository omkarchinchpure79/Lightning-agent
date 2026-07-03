"""
scrape_multi_source.py
Multi-source data collection for EduPath college profiles.

Sources and what each provides:
  1. AICTE Portal     OFFICIAL  — year_established, management_type, address, district
  2. NAAC Portal      OFFICIAL  — naac_grade, naac_score
  3. Nominatim/OSM    FREE      — latitude, longitude, address, district  (no API key)
  4. DuckDuckGo       SEARCH    — website_url discovery for colleges without one
  5. Wikipedia imgs   AGGREGATE — image_urls (only for 44 already-matched colleges)
  6. Shiksha.com      AGGREGATE — campus_area_acres, image_urls, annual_fee, year_established
  7. CollegeDunia     AGGREGATE — campus_area_acres, image_urls, year_established (fallback)

Source priority (higher wins on conflict):
  aicte_portal=6  naac_portal=6  official_website=4
  nominatim=3     wikipedia=3
  duckduckgo=2    shiksha=2      collegedunia=2

New columns added (via ALTER TABLE in setup_college_profiles.py):
  college_details: latitude REAL, longitude REAL, google_maps_url TEXT

Usage:
  python scripts/scrape_multi_source.py               # all sources, all colleges
  python scripts/scrape_multi_source.py --limit 10    # test on first 10
  python scripts/scrape_multi_source.py --code 06006  # single college
  python scripts/scrape_multi_source.py --source nominatim  # one source only
  python scripts/scrape_multi_source.py --summary     # stats only
  python scripts/scrape_multi_source.py --reset       # reset all progress to pending
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
RATE_LIMIT = 1.5   # polite: seconds between HTTP requests

SOURCE_PRIORITY = {
    "aicte_portal":     6,
    "naac_portal":      6,
    "official_website": 4,
    "nominatim":        3,
    "wikipedia":        3,
    "duckduckgo":       2,
    "shiksha":          2,
    "collegedunia":     2,
}

ALLOWED_FIELDS = {
    "naac_grade", "naac_score", "nirf_rank", "nba_branches", "is_autonomous",
    "year_established", "institution_type", "management_name",
    "annual_fee_min", "annual_fee_max", "tfws_available",
    "campus_area_acres", "has_hostel_boys", "has_hostel_girls", "has_sports", "has_wifi",
    "placement_pct", "avg_package_lpa", "highest_package_lpa", "top_recruiters",
    "placement_source", "address", "district", "website_url", "image_urls",
    "principal_name", "notes", "latitude", "longitude", "google_maps_url",
    "affiliated_university",
}

# Which sources to run (ordered)
ALL_SOURCES = ["aicte", "naac", "nominatim", "duckduckgo", "wikipedia_images", "shiksha", "collegedunia"]


# ---------------------------------------------------------------------------
# HTTP helper (browser UA, SSL fallback, retries)
# ---------------------------------------------------------------------------

def _get(url, timeout=20, retries=2, extra_headers=None, verify_ssl=True):
    try:
        import requests as req
        import urllib3
    except ImportError:
        print("ERROR: pip install requests beautifulsoup4")
        sys.exit(1)

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-IN,en;q=0.9",
        "Accept-Encoding": "gzip, deflate",
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
                urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
                try:
                    return req.get(url, headers=headers, timeout=timeout,
                                   allow_redirects=True, verify=False)
                except Exception:
                    pass
            return None
        except Exception:
            if attempt < retries:
                time.sleep(1)
    return None


def _post(url, data=None, json_data=None, timeout=20, extra_headers=None):
    try:
        import requests as req
    except ImportError:
        return None
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        ),
        "Accept": "application/json, text/html",
    }
    if extra_headers:
        headers.update(extra_headers)
    try:
        if json_data:
            return req.post(url, json=json_data, headers=headers, timeout=timeout)
        return req.post(url, data=data, headers=headers, timeout=timeout)
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Source 1: AICTE Portal
# ---------------------------------------------------------------------------

AICTE_API = "https://facilities.aicte-india.org/API/APIGET.php"

def _fetch_aicte_bulk():
    """
    Try AICTE's Angular dashboard API to get all Maharashtra engineering colleges.
    Returns list of dicts or [] on failure.
    """
    # Try known AICTE API endpoint patterns (Angular SPA backend)
    for payload in [
        {"filterState": "MAHARASHTRA", "filterProgramType": "Engineering and Technology"},
        {"state": "MAHARASHTRA", "program": "ENGINEERING AND TECHNOLOGY"},
        {"stateName": "Maharashtra", "programName": "Engineering"},
    ]:
        r = _post(AICTE_API, json_data=payload,
                  extra_headers={"Referer": "https://facilities.aicte-india.org/",
                                 "Origin": "https://facilities.aicte-india.org"})
        if r and r.status_code == 200:
            try:
                data = r.json()
                if isinstance(data, list) and len(data) > 10:
                    return data
                if isinstance(data, dict) and ("data" in data or "rows" in data):
                    rows = data.get("data") or data.get("rows") or []
                    if len(rows) > 10:
                        return rows
            except Exception:
                pass
        time.sleep(0.5)

    return []


def _parse_aicte_row(row):
    """Extract fields from one AICTE API row dict."""
    result = {}
    # Field names vary across API versions — try common aliases
    name_keys = ["InstituteName", "instituteName", "institute_name", "name", "collegeName"]
    year_keys = ["YearOfEstablishment", "yearEstd", "year_of_establishment", "estYear"]
    mgmt_keys = ["ManagementType", "managementType", "management_type", "Management"]
    addr_keys = ["FullAddress", "address", "fullAddress", "Address", "full_address"]
    dist_keys = ["District", "district", "districtName"]
    city_keys  = ["City", "city", "Town", "town"]

    for k in year_keys:
        if k in row:
            try:
                yr = int(str(row[k])[:4])
                if 1800 <= yr <= 2025:
                    result["year_established"] = yr
                    break
            except (ValueError, TypeError):
                pass

    for k in mgmt_keys:
        if k in row and row[k]:
            raw = str(row[k]).lower()
            if "government" in raw or "govt" in raw or "autonomous" in raw:
                result["institution_type"] = "gov"
                result["management_name"] = str(row[k])
            elif "aided" in raw:
                result["institution_type"] = "aided"
                result["management_name"] = str(row[k])
            elif "private" in raw or "unaided" in raw:
                result["institution_type"] = "pvt"
                result["management_name"] = str(row[k])
            break

    for k in addr_keys:
        if k in row and row[k]:
            result["address"] = str(row[k]).strip()
            break

    for k in dist_keys:
        if k in row and row[k]:
            result["district"] = str(row[k]).strip().title()
            break

    return result


_aicte_cache = None  # (college_name_lower -> fields dict)


def _build_aicte_cache():
    global _aicte_cache
    if _aicte_cache is not None:
        return

    print("  [AICTE] Fetching bulk data from AICTE portal ...", end=" ", flush=True)
    rows = _fetch_aicte_bulk()
    if not rows:
        print("API not accessible — will skip AICTE source.")
        _aicte_cache = {}
        return

    print(f"{len(rows)} institutions loaded.")
    name_keys = ["InstituteName", "instituteName", "institute_name", "name", "collegeName"]
    _aicte_cache = {}
    for row in rows:
        raw_name = None
        for k in name_keys:
            if k in row and row[k]:
                raw_name = str(row[k]).strip()
                break
        if not raw_name:
            continue
        key = raw_name.lower()
        _aicte_cache[key] = _parse_aicte_row(row)
    print(f"  [AICTE] Indexed {len(_aicte_cache)} colleges by name.")


def _fuzzy_key(name):
    """Normalize college name for fuzzy matching."""
    s = name.lower()
    s = re.sub(r"\b(of|and|the|pvt|ltd|trust|society|foundation|college|institute"
               r"|technology|engineering|sciences|management)\b", "", s)
    return re.sub(r"\s+", " ", s).strip()


def scrape_aicte(college_name, city):
    """Look up college in AICTE bulk cache. Returns dict or {}."""
    _build_aicte_cache()
    if not _aicte_cache:
        return {}

    # Exact match
    key = college_name.lower()
    if key in _aicte_cache:
        return _aicte_cache[key]

    # Fuzzy match: normalize and find best overlap
    fk = _fuzzy_key(college_name)
    fk_words = set(fk.split())
    best_score = 0
    best_data = {}
    for cache_name, data in _aicte_cache.items():
        ck_words = set(_fuzzy_key(cache_name).split())
        if not ck_words or not fk_words:
            continue
        inter = len(fk_words & ck_words)
        union = len(fk_words | ck_words)
        score = inter / union
        if score > best_score and score >= 0.55:
            best_score = score
            best_data = data
    return best_data


# ---------------------------------------------------------------------------
# Source 2: NAAC Portal
# ---------------------------------------------------------------------------

NAAC_SEARCH_URL = "https://naac.gov.in/en/user/grade"
NAAC_API_URL    = "https://naac.gov.in/index.php?option=com_apiportal&view=apiportal"


def scrape_naac(college_name, city):
    """
    Search naac.gov.in for grade/score. Returns dict or {}.
    Tries their public search API then falls back to HTML search.
    """
    try:
        from bs4 import BeautifulSoup
    except ImportError:
        return {}

    # Strategy 1: Try NAAC's known search endpoint
    search_url = "https://naac.gov.in/en/user/iiqa-search"
    clean_name = re.sub(r"\s+", " ", college_name).strip()

    for query in [clean_name, f"{clean_name} {city}"]:
        r = _get(f"{search_url}?search_query={urllib.parse.quote(query)}&state=21",
                 timeout=15)
        if r and r.status_code == 200:
            data = _parse_naac_html(r.text, college_name)
            if data:
                return data
        time.sleep(RATE_LIMIT)

    # Strategy 2: Try their grade table with state filter (Maharashtra = MH)
    r = _get(f"{NAAC_SEARCH_URL}?state=MH&institution_type=Engineering",
             timeout=15)
    if r and r.status_code == 200:
        data = _parse_naac_html(r.text, college_name)
        if data:
            return data

    return {}


def _parse_naac_html(html, target_name):
    """Parse NAAC search result HTML. Returns dict with naac_grade, naac_score or {}."""
    try:
        from bs4 import BeautifulSoup
    except ImportError:
        return {}

    soup = BeautifulSoup(html, "html.parser")
    target_lower = target_name.lower()

    # Look for table rows containing the college name
    for row in soup.find_all("tr"):
        cells = row.find_all(["td", "th"])
        if len(cells) < 3:
            continue
        row_text = " ".join(c.get_text(" ", strip=True) for c in cells)
        row_lower = row_text.lower()

        # Check if this row is about our college (loose name match)
        target_words = set(re.findall(r'\w+', target_lower)) - {
            "of", "and", "the", "college", "institute", "engineering", "technology", "s"
        }
        matched_words = sum(1 for w in target_words if w in row_lower)
        if len(target_words) < 2:
            continue
        if matched_words < max(2, len(target_words) // 2):
            continue

        # Extract grade (A++, A+, A, B++, B+, B, C)
        grade_m = re.search(r'\b(A\+\+|A\+|A|B\+\+|B\+|B|C)\b', row_text)
        score_m = re.search(r'\b(\d\.\d+)\b', row_text)
        result = {}
        if grade_m and grade_m.group(1) in ("A++", "A+", "A", "B++", "B+", "B", "C"):
            result["naac_grade"] = grade_m.group(1)
        if score_m:
            try:
                sc = float(score_m.group(1))
                if 0.0 < sc <= 4.0:
                    result["naac_score"] = sc
            except ValueError:
                pass
        if result:
            return result

    return {}


# ---------------------------------------------------------------------------
# Source 3: Nominatim (OpenStreetMap geocoding) — free, no API key
# ---------------------------------------------------------------------------

NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
NOMINATIM_UA  = "EduPath/1.0 (educational research; non-commercial; edupathmhtcet@gmail.com)"


def _nominatim_short_name(college_name):
    """
    Produce a shorter, Nominatim-friendly search string from a verbose college name.
    E.g. "P. R. Pote Patil College of Engineering & Management, Amravati"
       → "Pote Patil Engineering Amravati"
    """
    # Drop trailing city/address fragment after last comma
    name = re.split(r",\s*(?=[A-Z])", college_name)[0].strip()
    # Remove trust/management filler words
    noise = re.compile(
        r"\b(pvt|ltd|trust|society|foundation|sanstha|mandal|prasarak|shikshan"
        r"|charitable|pratishthan|of|and|the|a|an|for|in|at|&)\b",
        re.IGNORECASE
    )
    words = [w for w in re.findall(r"[A-Za-z][A-Za-z.'-]+", name)
             if not noise.match(w) and len(w) > 2]
    # Keep first 4 significant words
    return " ".join(words[:4])


def _nominatim_hit_to_result(hit, college_name, city):
    """Convert one Nominatim hit dict to college_details fields."""
    addr = hit.get("address", {})
    lat = float(hit["lat"])
    lon = float(hit["lon"])
    district = (addr.get("district") or addr.get("county")
                or addr.get("state_district") or "")
    district = district.replace(" District", "").strip()
    maps_url = (f"https://www.google.com/maps?q="
                + urllib.parse.quote(f"{college_name}, {city}")
                + f"&ll={lat},{lon}")
    result = {
        "latitude":        lat,
        "longitude":       lon,
        "google_maps_url": maps_url,
    }
    if hit.get("display_name"):
        result["address"] = hit["display_name"]
    if district:
        result["district"] = district
    return result


def _nominatim_search(query):
    """One Nominatim API call. Returns list of hits or []."""
    url = (NOMINATIM_URL
           + "?q=" + urllib.parse.quote(query)
           + "&format=json&limit=5&addressdetails=1&accept-language=en")
    r = _get(url, timeout=15,
             extra_headers={"User-Agent": NOMINATIM_UA, "Accept": "application/json"})
    time.sleep(RATE_LIMIT)  # Nominatim policy: max 1 req/sec
    if not r or r.status_code != 200:
        return []
    try:
        return r.json()
    except Exception:
        return []


def scrape_nominatim(college_name, city):
    """
    Geocode college via Nominatim. Returns dict with latitude, longitude, address, district.
    Tries multiple query strategies to maximise hit rate on obscure Indian college names.
    """
    short = _nominatim_short_name(college_name)
    city_q = city or ""

    queries = [
        f"{college_name}, {city_q}, Maharashtra, India",       # exact full name
        f"{short} college {city_q}, Maharashtra, India",       # short + generic
        f"{short} institute {city_q}, Maharashtra, India",     # short + institute
        f"{short} {city_q} Maharashtra",                       # very short
    ]

    edu_types = {"university", "college", "school", "education",
                 "institute", "campus", "training"}
    edu_classes = {"amenity", "building", "education"}

    for query in queries:
        hits = _nominatim_search(query)
        if not hits:
            continue

        # Prefer educational-type results in Maharashtra
        for hit in hits:
            addr = hit.get("address", {})
            state = addr.get("state", "").lower()
            if "maharashtra" not in state:
                continue
            cls = hit.get("class", "")
            typ = hit.get("type", "")
            if cls in edu_classes or typ in edu_types:
                return _nominatim_hit_to_result(hit, college_name, city_q)

        # Fall back to first Maharashtra result if no educational type found
        for hit in hits:
            addr = hit.get("address", {})
            state = addr.get("state", "").lower()
            if "maharashtra" in state:
                # Make sure the city matches roughly
                hit_city = (addr.get("city") or addr.get("town") or
                            addr.get("village") or "").lower()
                if not city_q or not hit_city or city_q.lower()[:4] in hit_city:
                    return _nominatim_hit_to_result(hit, college_name, city_q)

    return {}


# ---------------------------------------------------------------------------
# Source 4: Website URL discovery via .ac.in guessing + DTE Maharashtra
# ---------------------------------------------------------------------------

def find_website_duckduckgo(college_name, city):
    """
    Discover official website by guessing .ac.in/.edu.in URL patterns and
    verifying they respond. Tries DTE Maharashtra listing as fallback.
    Returns {"website_url": "..."} or {}.
    """
    # Strategy A: Known domain lookup + pattern guessing
    candidates = _guess_acinurls(college_name, city)
    for candidate_url in candidates:
        r = _get(candidate_url, timeout=8)
        if r and r.status_code in (200, 301, 302, 403):
            final_url = r.url if r.status_code in (301, 302) else candidate_url
            if r.status_code == 200 and len(r.text) < 300:
                continue  # parked/empty domain
            return {"website_url": final_url.rstrip("/")}
        time.sleep(0.4)

    # Strategy B: DTE Maharashtra college list page
    dte_result = _search_dte_maharashtra(college_name)
    if dte_result:
        return dte_result

    return {}


def _guess_acinurls(college_name, city):
    """
    Generate candidate .ac.in / .edu.in URLs from a college name.
    """
    SKIP = {"of", "and", "the", "a", "an", "in", "at", "for", "pvt",
            "ltd", "trust", "society", "foundation", "sanstha", "mandal",
            "shikshan", "prasarak", "pratishthan", "charitable", "management"}

    clean = college_name.lower().replace("'","").replace('"',"")
    clean = re.sub(r"[.,&\-]", "", clean)
    clean = re.sub(r"\s+", " ", clean).strip()
    words = [w for w in clean.split() if w not in SKIP and len(w) > 1]
    if not words:
        return []

    city_l = (city or "").lower()

    # Known colleges: hard-coded domain mappings
    KNOWN = {
        "college of engineering pune": "coep.ac.in",
        "veermata jijabai technological": "vjti.ac.in",
        "pune institute of computer technology": "pict.edu",
        "vishwakarma institute of technology": "vit.edu.in",
        "mit college of engineering": "mitcoe.edu.in",
        "walchand college of engineering": "walchandsangli.ac.in",
        "government college of engineering aurangabad": "gcea.ac.in",
        "government college of engineering nagpur": "gcoen.ac.in",
        "government college of engineering amravati": "gcoea.ac.in",
        "government college of engineering karad": "gcekarad.ac.in",
        "government college of engineering chandrapur": "gcoec.ac.in",
        "institute of chemical technology": "ictmumbai.ac.in",
        "dr babasaheb ambedkar technological university": "dbatu.ac.in",
    }
    for key, domain in KNOWN.items():
        if key in clean:
            return [f"https://www.{domain}", f"https://{domain}"]

    initials = "".join(w[0] for w in words)
    first = words[0]
    slug2 = "".join(words[:2])
    slug3 = "".join(words[:3])

    candidates = []
    # Initials-based (most common)
    if 2 <= len(initials) <= 8:
        candidates += [f"https://www.{initials}.ac.in", f"https://{initials}.ac.in"]
    # First-word-based
    if 3 <= len(first) <= 10:
        candidates += [f"https://www.{first}.ac.in", f"https://{first}.edu.in"]
    # Slug-based
    if 4 <= len(slug2) <= 12:
        candidates += [f"https://www.{slug2}.ac.in", f"https://www.{slug2}.edu.in"]
    if 4 <= len(slug3) <= 16:
        candidates.append(f"https://www.{slug3}.ac.in")

    return candidates[:10]


_dte_college_cache = None  # (name_fragment_lower -> url)


def _search_dte_maharashtra(college_name):
    """Try DTE Maharashtra college listing. Returns {"website_url": ...} or {}."""
    global _dte_college_cache
    try:
        from bs4 import BeautifulSoup
    except ImportError:
        return {}

    if _dte_college_cache is None:
        _dte_college_cache = {}
        for url in [
            "https://dtemaharashtra.gov.in/engineering/StaticPages/CollegeList.aspx",
            "https://dtemaharashtra.gov.in/Autonomous/CollegeCodeandNamelist.aspx",
        ]:
            r = _get(url, timeout=20)
            if r and r.status_code == 200:
                try:
                    soup = BeautifulSoup(r.text, "html.parser")
                    for row in soup.find_all("tr"):
                        cells = row.find_all("td")
                        if len(cells) < 2:
                            continue
                        row_text = cells[0].get_text(" ", strip=True).lower()
                        for a in row.find_all("a", href=True):
                            href = a["href"]
                            if href.startswith("http"):
                                _dte_college_cache[row_text] = href
                except Exception:
                    pass
                break

    if not _dte_college_cache:
        return {}

    target_words = set(re.findall(r"\w+", college_name.lower())) - {
        "of", "and", "the", "college", "institute", "engineering", "s", "technology"
    }
    best_score = 0
    best_url = None
    for name_fragment, url in _dte_college_cache.items():
        row_words = set(re.findall(r"\w+", name_fragment))
        if not row_words:
            continue
        matched = len(target_words & row_words)
        score = matched / max(len(target_words), 1)
        if score > best_score and score >= 0.5:
            best_score = score
            best_url = url
    if best_url:
        return {"website_url": best_url.rstrip("/")}
    return {}


# ---------------------------------------------------------------------------
# Source 5: Wikipedia images (for already-matched colleges only)
# ---------------------------------------------------------------------------

def scrape_wikipedia_images(wikipedia_url):
    """
    Extract main image(s) from a Wikipedia college page.
    Returns {"image_urls": "[url1, url2]"} or {}.
    """
    if not wikipedia_url:
        return {}

    title = urllib.parse.unquote(wikipedia_url.split("/wiki/")[-1])
    url = (
        "https://en.wikipedia.org/w/api.php"
        "?action=query&titles=" + urllib.parse.quote(title)
        + "&prop=pageimages&pithumbsize=600&format=json&origin=*"
    )
    r = _get(url, timeout=15,
             extra_headers={"User-Agent":
                            "EduPath/1.0 (educational; edupathmhtcet@gmail.com)"})
    if not r or r.status_code != 200:
        return {}

    try:
        data = r.json()
    except Exception:
        return {}

    for page in data.get("query", {}).get("pages", {}).values():
        thumb = page.get("thumbnail", {}).get("source")
        if thumb:
            # Get full resolution from Commons
            full = thumb.replace("/thumb/", "/").rsplit("/", 1)[0]
            urls = [full, thumb]
            return {"image_urls": json.dumps(urls)}

    return {}


# ---------------------------------------------------------------------------
# Source 6: Shiksha.com
# ---------------------------------------------------------------------------

def scrape_shiksha(college_name, city):
    """
    Search Shiksha.com for college page and extract profile data.
    Shiksha uses Akamai WAF so may return 403 — returns {} on block.
    """
    try:
        from bs4 import BeautifulSoup
    except ImportError:
        return {}

    # Search for college page
    query = f"{college_name} {city} engineering"
    search_url = "https://www.shiksha.com/search?q=" + urllib.parse.quote(query) + "&type=college"

    r = _get(search_url, timeout=20, extra_headers={
        "Referer": "https://www.shiksha.com/",
        "Accept": "text/html,application/xhtml+xml",
    })
    if not r or r.status_code in (403, 429, 503):
        return {}
    if r.status_code != 200:
        return {}

    try:
        soup = BeautifulSoup(r.text, "html.parser")
    except Exception:
        return {}

    # Find first college result link
    college_link = None
    for a in soup.select("a[href*='/college/']"):
        href = a.get("href", "")
        if "/college/" in href and "/overview" in href:
            college_link = href if href.startswith("http") else "https://www.shiksha.com" + href
            break
    if not a:
        for a in soup.select("a[href*='/overview']"):
            href = a.get("href", "")
            if href:
                college_link = href if href.startswith("http") else "https://www.shiksha.com" + href
                break

    if not college_link:
        return {}

    time.sleep(RATE_LIMIT)
    r2 = _get(college_link, timeout=20, extra_headers={
        "Referer": search_url,
    })
    if not r2 or r2.status_code != 200:
        return {}

    return _parse_shiksha_page(r2.text)


def _parse_shiksha_page(html):
    """Extract fields from a Shiksha college overview page."""
    try:
        from bs4 import BeautifulSoup
    except ImportError:
        return {}

    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style"]):
        tag.decompose()
    text = soup.get_text(" ", strip=True)
    result = {}

    # Year established
    yr_m = re.search(r'(?:Established|Founded|Est\.?|Year of Establishment)[:\s]*(\d{4})',
                     text, re.IGNORECASE)
    if yr_m:
        yr = int(yr_m.group(1))
        if 1800 <= yr <= 2025:
            result["year_established"] = yr

    # Campus area
    area_m = re.search(r'([\d.]+)\s*[Aa]cres?', text)
    if area_m:
        try:
            a = float(area_m.group(1))
            if 0.5 <= a <= 5000:
                result["campus_area_acres"] = a
        except ValueError:
            pass

    # Fees
    fee_m = re.search(r'(?:Annual|Total|Tuition)\s+[Ff]ee[s]?\s*[:\-]?\s*(?:INR|₹|Rs\.?)?\s*([\d,]+)',
                      text)
    if fee_m:
        try:
            fee = float(fee_m.group(1).replace(",", ""))
            if 10_000 <= fee <= 30_00_000:
                result["annual_fee_min"] = fee
        except ValueError:
            pass

    # Images: look for og:image or JSON-LD images
    imgs = []
    for meta in soup.find_all("meta", property="og:image"):
        content = meta.get("content", "")
        if content and content.startswith("http"):
            imgs.append(content)

    for img in soup.select("img.college-image, img.campus-image, img[class*='campus'], img[class*='college']"):
        src = img.get("src") or img.get("data-src", "")
        if src and src.startswith("http") and src not in imgs:
            imgs.append(src)

    if imgs:
        result["image_urls"] = json.dumps(imgs[:5])

    return result


# ---------------------------------------------------------------------------
# Source 7: CollegeDunia
# ---------------------------------------------------------------------------

def scrape_collegedunia(college_name, city):
    """
    Search CollegeDunia for college profile. Fallback after Shiksha.
    """
    try:
        from bs4 import BeautifulSoup
    except ImportError:
        return {}

    query = f"{college_name} {city} engineering"
    search_url = ("https://collegedunia.com/search?query="
                  + urllib.parse.quote(query))

    r = _get(search_url, timeout=20, extra_headers={
        "Referer": "https://collegedunia.com/",
    })
    if not r or r.status_code not in (200,):
        return {}

    try:
        soup = BeautifulSoup(r.text, "html.parser")
    except Exception:
        return {}

    # Find first result link
    college_link = None
    for a in soup.select("a[href*='/college/']"):
        href = a.get("href", "")
        if "/college/" in href and len(href) > 20:
            college_link = href if href.startswith("http") else "https://collegedunia.com" + href
            break

    if not college_link:
        return {}

    time.sleep(RATE_LIMIT)
    r2 = _get(college_link, timeout=20, extra_headers={"Referer": search_url})
    if not r2 or r2.status_code != 200:
        return {}

    return _parse_collegedunia_page(r2.text)


def _parse_collegedunia_page(html):
    """Extract fields from a CollegeDunia college page."""
    try:
        from bs4 import BeautifulSoup
    except ImportError:
        return {}

    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style"]):
        tag.decompose()
    text = soup.get_text(" ", strip=True)
    result = {}

    yr_m = re.search(r'(?:Established|Founded)[:\s]*(\d{4})', text, re.IGNORECASE)
    if yr_m:
        yr = int(yr_m.group(1))
        if 1800 <= yr <= 2025:
            result["year_established"] = yr

    area_m = re.search(r'([\d.]+)\s*[Aa]cres?', text)
    if area_m:
        try:
            a = float(area_m.group(1))
            if 0.5 <= a <= 5000:
                result["campus_area_acres"] = a
        except ValueError:
            pass

    imgs = []
    for meta in soup.find_all("meta", property="og:image"):
        src = meta.get("content", "")
        if src and src.startswith("http"):
            imgs.append(src)
    for img in soup.select("img[class*='college'], img[class*='campus']"):
        src = img.get("src") or img.get("data-src", "")
        if src and src.startswith("http") and src not in imgs:
            imgs.append(src)
    if imgs:
        result["image_urls"] = json.dumps(imgs[:5])

    return result


# ---------------------------------------------------------------------------
# DB write with source priority (same logic as scrape_all_colleges.py)
# ---------------------------------------------------------------------------

def write_with_source(conn, code, fields, source_type, url, is_official):
    """Write fields respecting source priority. Returns count written."""
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
            "SELECT source_type FROM college_data_sources "
            "WHERE college_code = ? AND field_name = ?",
            (code, field)
        )
        existing = cur.fetchone()
        if existing and SOURCE_PRIORITY.get(existing[0], 1) > my_priority:
            continue

        try:
            cur.execute(
                f"UPDATE college_details SET {field} = ?, last_updated = ? "
                f"WHERE college_code = ?",
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
# Per-college orchestration
# ---------------------------------------------------------------------------

def process_one(conn, code, name, city, sources_to_run, verbose=True):
    """Run all requested sources for one college. Returns total fields written."""
    cur = conn.cursor()
    fields_total = 0

    # Get current state
    cur.execute(
        "SELECT wikipedia_url, aicte_done, naac_done, nominatim_done, "
        "duckduckgo_done, wiki_images_done, shiksha_done, collegedunia_done "
        "FROM scrape_progress WHERE college_code = ?",
        (code,)
    )
    sp = cur.fetchone()
    wiki_url       = sp[0] if sp else None
    aicte_done     = bool(sp[1]) if sp else False
    naac_done      = bool(sp[2]) if sp else False
    nominatim_done = bool(sp[3]) if sp else False
    ddg_done       = bool(sp[4]) if sp else False
    wiki_img_done  = bool(sp[5]) if sp else False
    shiksha_done   = bool(sp[6]) if sp else False
    cd_done        = bool(sp[7]) if sp else False

    cur.execute("SELECT website_url FROM college_details WHERE college_code = ?", (code,))
    det = cur.fetchone()
    website_url = det[0] if det else None

    # ── AICTE ──────────────────────────────────────────────────────────────
    if "aicte" in sources_to_run and not aicte_done:
        if verbose:
            print(f"    AICTE lookup ...", end=" ", flush=True)
        data = scrape_aicte(name, city or "")
        if data:
            n = write_with_source(conn, code, data, "aicte_portal",
                                  AICTE_API, is_official=True)
            fields_total += n
            if verbose:
                print(f"{n} fields {list(data.keys())}")
        else:
            if verbose:
                print("no match")
        cur.execute("UPDATE scrape_progress SET aicte_done=1 WHERE college_code=?", (code,))
        conn.commit()

    # ── NAAC ───────────────────────────────────────────────────────────────
    if "naac" in sources_to_run and not naac_done:
        if verbose:
            print(f"    NAAC portal ...", end=" ", flush=True)
        data = scrape_naac(name, city or "")
        if data:
            n = write_with_source(conn, code, data, "naac_portal",
                                  NAAC_SEARCH_URL, is_official=True)
            fields_total += n
            if verbose:
                print(f"{n} fields {list(data.keys())}")
        else:
            if verbose:
                print("no match")
        cur.execute("UPDATE scrape_progress SET naac_done=1 WHERE college_code=?", (code,))
        conn.commit()
        time.sleep(RATE_LIMIT)

    # ── Nominatim ──────────────────────────────────────────────────────────
    if "nominatim" in sources_to_run and not nominatim_done:
        if verbose:
            print(f"    Nominatim geocoding ...", end=" ", flush=True)
        data = scrape_nominatim(name, city or "")
        if data:
            n = write_with_source(conn, code, data, "nominatim",
                                  NOMINATIM_URL, is_official=False)
            fields_total += n
            if verbose:
                lat = data.get("latitude", "")
                lon = data.get("longitude", "")
                print(f"{n} fields  lat={lat:.4f}, lon={lon:.4f}" if lat else f"{n} fields")
        else:
            if verbose:
                print("no result")
        cur.execute("UPDATE scrape_progress SET nominatim_done=1 WHERE college_code=?", (code,))
        conn.commit()
        time.sleep(RATE_LIMIT)

    # ── DuckDuckGo (website discovery) ────────────────────────────────────
    if "duckduckgo" in sources_to_run and not ddg_done and not website_url:
        if verbose:
            print(f"    DuckDuckGo website search ...", end=" ", flush=True)
        data = find_website_duckduckgo(name, city or "")
        if data:
            n = write_with_source(conn, code, data, "duckduckgo",
                                  "https://html.duckduckgo.com/html/", is_official=False)
            fields_total += n
            website_url = data.get("website_url")
            if verbose:
                print(f"found: {website_url}")
        else:
            if verbose:
                print("not found")
        cur.execute("UPDATE scrape_progress SET duckduckgo_done=1 WHERE college_code=?", (code,))
        conn.commit()
        time.sleep(RATE_LIMIT)

    # ── Wikipedia images ───────────────────────────────────────────────────
    if "wikipedia_images" in sources_to_run and not wiki_img_done and wiki_url:
        if verbose:
            print(f"    Wikipedia images ...", end=" ", flush=True)
        data = scrape_wikipedia_images(wiki_url)
        if data:
            n = write_with_source(conn, code, data, "wikipedia",
                                  wiki_url, is_official=False)
            fields_total += n
            if verbose:
                print(f"{n} fields")
        else:
            if verbose:
                print("no images")
        cur.execute("UPDATE scrape_progress SET wiki_images_done=1 WHERE college_code=?", (code,))
        conn.commit()

    # ── Shiksha.com ────────────────────────────────────────────────────────
    if "shiksha" in sources_to_run and not shiksha_done:
        if verbose:
            print(f"    Shiksha.com ...", end=" ", flush=True)
        data = scrape_shiksha(name, city or "")
        if data:
            n = write_with_source(conn, code, data, "shiksha",
                                  "https://www.shiksha.com/", is_official=False)
            fields_total += n
            if verbose:
                print(f"{n} fields {list(data.keys())}")
        else:
            if verbose:
                print("blocked or no match")
        cur.execute("UPDATE scrape_progress SET shiksha_done=1 WHERE college_code=?", (code,))
        conn.commit()
        time.sleep(RATE_LIMIT)

    # ── CollegeDunia ───────────────────────────────────────────────────────
    if "collegedunia" in sources_to_run and not cd_done:
        if verbose:
            print(f"    CollegeDunia ...", end=" ", flush=True)
        data = scrape_collegedunia(name, city or "")
        if data:
            n = write_with_source(conn, code, data, "collegedunia",
                                  "https://collegedunia.com/", is_official=False)
            fields_total += n
            if verbose:
                print(f"{n} fields {list(data.keys())}")
        else:
            if verbose:
                print("blocked or no match")
        cur.execute("UPDATE scrape_progress SET collegedunia_done=1 WHERE college_code=?", (code,))
        conn.commit()
        time.sleep(RATE_LIMIT)

    return fields_total


# ---------------------------------------------------------------------------
# Migrations: add new columns
# ---------------------------------------------------------------------------

def _apply_migrations(conn):
    """Add new columns to college_details and scrape_progress if missing."""
    cur = conn.cursor()

    # college_details: new location columns
    cur.execute("PRAGMA table_info(college_details)")
    cd_cols = {r[1] for r in cur.fetchall()}
    for col, typ in [("latitude", "REAL"), ("longitude", "REAL"),
                     ("google_maps_url", "TEXT")]:
        if col not in cd_cols:
            cur.execute(f"ALTER TABLE college_details ADD COLUMN {col} {typ}")
            print(f"  Migrated college_details: added {col} column.")

    # scrape_progress: add per-source completion flags
    cur.execute("PRAGMA table_info(scrape_progress)")
    sp_cols = {r[1] for r in cur.fetchall()}
    for col in ["aicte_done", "naac_done", "nominatim_done",
                "duckduckgo_done", "wiki_images_done", "shiksha_done", "collegedunia_done"]:
        if col not in sp_cols:
            cur.execute(f"ALTER TABLE scrape_progress ADD COLUMN {col} INTEGER DEFAULT 0")
            print(f"  Migrated scrape_progress: added {col} column.")

    conn.commit()


# ---------------------------------------------------------------------------
# Progress summary
# ---------------------------------------------------------------------------

def print_coverage(conn):
    cur = conn.cursor()
    cur.execute("""SELECT
        COUNT(*) total,
        SUM(CASE WHEN year_established IS NOT NULL THEN 1 ELSE 0 END) year_est,
        SUM(CASE WHEN campus_area_acres IS NOT NULL THEN 1 ELSE 0 END) campus,
        SUM(CASE WHEN naac_grade IS NOT NULL THEN 1 ELSE 0 END) naac,
        SUM(CASE WHEN website_url IS NOT NULL THEN 1 ELSE 0 END) website,
        SUM(CASE WHEN address IS NOT NULL THEN 1 ELSE 0 END) addr,
        SUM(CASE WHEN latitude IS NOT NULL THEN 1 ELSE 0 END) lat,
        SUM(CASE WHEN image_urls IS NOT NULL THEN 1 ELSE 0 END) imgs,
        SUM(CASE WHEN district IS NOT NULL THEN 1 ELSE 0 END) dist
    FROM college_details""")
    row = cur.fetchone()
    if row:
        total = row[0]
        print(f"\n  Coverage (out of {total} colleges):")
        labels = ["year_established", "campus_area_acres", "naac_grade",
                  "website_url", "address", "latitude", "image_urls", "district"]
        for i, lbl in enumerate(labels, 1):
            print(f"    {lbl:<22}: {row[i]:>4} / {total}")

    # Source breakdown
    cur.execute("""SELECT source_type, COUNT(*) n
                   FROM college_data_sources GROUP BY source_type ORDER BY n DESC""")
    rows = cur.fetchall()
    if rows:
        print(f"\n  Fields by source:")
        for src, n in rows:
            print(f"    {src:<20}: {n:>5} field-writes")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    args = sys.argv[1:]
    reset        = "--reset" in args
    summary_only = "--summary" in args
    single_code  = None
    limit        = None
    source_filter = None

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
                pass

    if "--source" in args:
        idx = args.index("--source")
        if idx + 1 < len(args):
            source_filter = [args[idx + 1]]

    sources_to_run = source_filter or ALL_SOURCES

    if not os.path.exists(DB_PATH):
        print(f"ERROR: {DB_PATH} not found. Run load_db.py first.")
        sys.exit(1)

    conn = sqlite3.connect(DB_PATH)

    _apply_migrations(conn)

    if summary_only:
        print_coverage(conn)
        conn.close()
        return

    if reset:
        cols = ["aicte_done", "naac_done", "nominatim_done",
                "duckduckgo_done", "wiki_images_done", "shiksha_done", "collegedunia_done"]
        reset_sql = ", ".join(f"{c}=0" for c in cols)
        conn.execute(f"UPDATE scrape_progress SET {reset_sql}")
        conn.commit()
        print("Reset all multi-source progress flags.")

    cur = conn.cursor()
    if single_code:
        cur.execute("""
            SELECT sp.college_code, sp.college_name, c.city
            FROM scrape_progress sp
            LEFT JOIN colleges c ON c.college_code = sp.college_code
            WHERE sp.college_code = ?
        """, (single_code,))
    else:
        # Build WHERE clause: at least one source is not done
        done_cols  = {
            "aicte":           "aicte_done",
            "naac":            "naac_done",
            "nominatim":       "nominatim_done",
            "duckduckgo":      "duckduckgo_done",
            "wikipedia_images":"wiki_images_done",
            "shiksha":         "shiksha_done",
            "collegedunia":    "collegedunia_done",
        }
        conditions = " OR ".join(
            f"COALESCE({done_cols[s]}, 0) = 0"
            for s in sources_to_run if s in done_cols
        )
        if not conditions:
            conditions = "1=1"
        cur.execute(f"""
            SELECT sp.college_code, sp.college_name, c.city
            FROM scrape_progress sp
            LEFT JOIN colleges c ON c.college_code = sp.college_code
            WHERE {conditions}
            ORDER BY sp.college_code
        """)

    colleges = cur.fetchall()
    if limit:
        colleges = colleges[:limit]

    if not colleges:
        print("All done. Use --reset to re-run sources.")
        print_coverage(conn)
        conn.close()
        return

    print(f"\nEduPath Multi-Source Scraper")
    print(f"  Sources: {', '.join(sources_to_run)}")
    print(f"  Colleges: {len(colleges)}")
    print(f"  Rate limit: {RATE_LIMIT}s\n")

    total_fields = 0

    for i, (code, name, city) in enumerate(colleges, 1):
        print(f"\n[{i}/{len(colleges)}] {name[:60]} | {city or '?'} | {code}")
        try:
            n = process_one(conn, code, name, city, sources_to_run)
            total_fields += n
        except KeyboardInterrupt:
            print("\n\nInterrupted — progress saved. Run again to resume.")
            break
        except Exception as e:
            print(f"    ERROR: {e}")

        if i % 50 == 0:
            print_coverage(conn)

    print(f"\n{'='*65}")
    print(f"Done. Total fields written this run: {total_fields}")
    print_coverage(conn)
    conn.close()
    print("\nNext: python -m unittest discover -s tests")


if __name__ == "__main__":
    main()
