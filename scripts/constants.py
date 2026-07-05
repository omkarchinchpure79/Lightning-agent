"""
Shared constants for the EduPath prediction engine.
Import from this module — never redefine these in individual scripts.
"""

import re
import statistics

# ---------------------------------------------------------------------------
# Category fallback chains
# When no cutoff data exists for the exact category, fall back to the broader
# state-level category. Pattern: H (Home Univ) -> S (State), O (Other Univ) -> S (State)
#
# IMPORTANT: The actual DB category code for EWS seats is "EWS", not "GEWS".
# GEWS is listed in CAP brochures but "EWS" is what appears in the actual PDF data.
# ---------------------------------------------------------------------------
CATEGORY_FALLBACKS = {
    # --- General Open ---
    "GOPENH":  ["GOPENS"],
    "GOPENO":  ["GOPENS"],

    # --- General SC ---
    "GSCH":    ["GSCS"],
    "GSCO":    ["GSCS"],

    # --- General ST ---
    "GSTH":    ["GSTS"],
    "GSTO":    ["GSTS"],

    # --- General OBC ---
    "GOBCH":   ["GOBCS"],
    "GOBCO":   ["GOBCS"],

    # --- General VJ/DT (Vimukta Jati / Denotified Tribes) ---
    "GVJH":    ["GVJS"],
    "GVJO":    ["GVJS"],

    # --- General NT1/NT2/NT3 (Nomadic Tribes) ---
    "GNT1H":   ["GNT1S"],
    "GNT1O":   ["GNT1S"],
    "GNT2H":   ["GNT2S"],
    "GNT2O":   ["GNT2S"],
    "GNT3H":   ["GNT3S"],
    "GNT3O":   ["GNT3S"],

    # --- General SBC (Special Backward Class) ---
    "GSEBCH":  ["GSEBCS"],
    "GSEBCO":  ["GSEBCS"],

    # --- EWS alias: GEWS is the brochure name; actual DB category code is EWS ---
    "GEWS":    ["EWS"],

    # --- Ladies Open ---
    "LOPENH":  ["LOPENS"],
    "LOPENO":  ["LOPENS"],

    # --- Ladies SC ---
    "LSCH":    ["LSCS"],
    "LSCO":    ["LSCS"],

    # --- Ladies ST ---
    "LSTH":    ["LSTS"],
    "LSTO":    ["LSTS"],

    # --- Ladies OBC ---
    "LOBCH":   ["LOBCS"],
    "LOBCO":   ["LOBCS"],

    # --- Ladies VJ/DT ---
    "LVJH":    ["LVJS"],
    "LVJO":    ["LVJS"],

    # --- Ladies NT1/NT2/NT3 ---
    "LNT1H":   ["LNT1S"],
    "LNT1O":   ["LNT1S"],
    "LNT2H":   ["LNT2S"],
    "LNT2O":   ["LNT2S"],
    "LNT3H":   ["LNT3S"],
    "LNT3O":   ["LNT3S"],

    # --- Ladies SBC ---
    "LSEBCH":  ["LSEBCS"],
    "LSEBCO":  ["LSEBCS"],

    # --- PwD Open ---
    "PWDOPENH": ["PWDOPENS"],

    # --- PwD OBC ---
    "PWDOBCH":  ["PWDOBCS"],

    # --- PwD SC ---
    "PWDSCH":   ["PWDSCS"],

    # --- PwD SBC ---
    "PWDSEBCH": ["PWDSEBCS"],

    # --- PwD reserved NT1/NT2/NT3/VJ/SC/SBC/ST (small counts) ---
    "PWDRNT1H":  ["PWDRNT1S"],
    "PWDRNT2H":  ["PWDRNT2S"],
    "PWDROBCH":  ["PWDROBCS"],
    "PWDRSCH":   ["PWDRSCS"],
    "PWDRSEBCH": ["PWDRSEBCS"],
    "PWDRSTH":   ["PWDRSTS"],
    "PWDRVJH":   ["PWDRVJS"],

    # --- Defence OBC Other ---
    "DEFOBCO":   ["DEFOBCS"],
}

# Recency weights for probability calculation: 2025 data matters most.
# Default weight 0.25 is used for any year not listed (e.g., future 2026 actual data).
YEAR_WEIGHTS = {2023: 0.20, 2024: 0.35, 2025: 0.45}

# ---------------------------------------------------------------------------
# Cross-year branch identity
#
# The SAME physical (college, branch) appears under DIFFERENT codes/names each
# year because CET Cell re-numbers things. To correlate 2023/2024/2025 data we
# need ONE stable key. canonical_branch_key() is the single source of truth —
# both generate_predictions.py and predict.py MUST use it so generation and
# lookup always agree (mismatched keys were the root cause of the COEP bug).
#
# Rule:
#  - Normal colleges: 2024+ only ZERO-PADS the code (4-digit college XXXX ->
#    0XXXX, so branch_code 'NNNN...' -> '0NNNN...'). Stripping leading zeros
#    gives an identical key across years. Verified: 331/337 colleges + handles
#    the 17 cases where the NAME changed but the code didn't (e.g. PICT).
#  - Re-coded colleges (COEP, etc.): CET Cell fully renumbered the college code
#    AND the per-branch course suffix (e.g. 6006 -> 16006, suffix 24510 -> 24210),
#    so the code is useless across years. Fall back to joining by college
#    substring + branch name. The substring must appear in the name in BOTH years.
#
# KNOWN LIMITATION: 5 other re-coded colleges (LIT Nagpur 4005->14005, RCOEM,
# Vishwakarma IIT Pune, Nutan Talegaon, DYP-IEMR Akurdi) changed both code and
# name and are NOT auto-merged. Their 2023 data is siloed; predictions use
# 2024+2025 (medium confidence). Guessing their crosswalk risks wrong merges,
# so they are documented rather than aliased. See CLAUDE.md "Known Data Quirks".
# ---------------------------------------------------------------------------

# Colleges CET Cell fully re-coded; join these by NAME, not branch_code.
# The substring must be present in the college_name in every year of data.
RECODED_COLLEGES = (
    "COEP Technological University",
)

# Within a re-coded college, branches whose NAME also changed across years.
# Maps any historical branch name -> the canonical (latest) name. Only applied
# inside RECODED_COLLEGES, so it never disturbs branches at normally-coded colleges.
BRANCH_NAME_ALIASES = {
    "Computer Engineering": "Computer Science and Engineering",  # COEP 2023 -> 2024+
}


# Seat-sub-type variant suffix on a course code. The SAME physical branch at one
# college is issued multiple course codes for different seat sub-types, e.g.
# E&TC at college 03033:  ...37210 (base) / ...37213K / ...37290L / ...37293LK.
# The variant = optional trailing letters (K/L/LK/U/F...) PLUS the 2 seat-type
# digits before them. Stripping both collapses the variants to one identity.
# Verified across the whole DB: this never merges two differently-NAMED branches.
_SEAT_VARIANT_LETTERS = re.compile(r"[A-Za-z]+$")


def _strip_seat_variant(code):
    """branch_code (leading zeros already stripped) -> physical-branch course root."""
    code = _SEAT_VARIANT_LETTERS.sub("", code)   # drop trailing letters (K/L/LK/U/F)
    return code[:-2] if len(code) > 2 else code   # drop the 2 seat-type digits


def canonical_branch_key(college_name, branch_name, branch_code):
    """
    Return a stable string identity for a physical (college, branch) that is the
    same across all years AND across seat-sub-type code variants, regardless of
    CET Cell's annual code/name churn.

    Two disjoint key namespaces so the schemes can never collide:
      "NAME::<college frag>::<canonical branch>"      for re-coded colleges
      "CODE::<course root, seat-variant stripped>"     for everything else
    """
    for frag in RECODED_COLLEGES:
        if frag in college_name:
            name = BRANCH_NAME_ALIASES.get(branch_name, branch_name)
            return f"NAME::{frag}::{name}"
    return "CODE::" + _strip_seat_variant(branch_code.lstrip("0"))


# Must equal len(SUBSET_DEFINITIONS) in setup_college_profiles.py
TOTAL_SUBSETS = 21

# Open-seat categories treated as one "general demand" signal for trend lines
# and for the selectivity score (see score_colleges.py). H/O/S are the same
# underlying demand for a general-category seat, just split by home-university
# jurisdiction — taking the toughest of the three per college/branch/year is
# the correct read of "how hard is this seat to get."
OPEN_CATEGORIES = ("GOPENH", "GOPENS", "GOPENO")


def canonical_college_key(college_code, college_name):
    """
    Stable identity for a physical college across CET Cell's annual code/name
    churn — the same problem canonical_branch_key() solves for branches, one
    level up. Two fragments of the SAME college (e.g. code '2008' before a
    district rename vs '02008' after, or '6281'/'06281' across the 2023->2024
    4-digit->5-digit re-padding) must resolve to one key so scoring, profile
    lookups, etc. aggregate all of a college's data instead of splitting it.

    Rule (mirrors canonical_branch_key):
      - RECODED_COLLEGES (code AND name both churned) -> key by name fragment.
      - Everything else -> key by college_code with leading zeros stripped.
        This is safe because CET Cell's only systematic change for these
        colleges is 4-digit -> 5-digit zero-padding; the digits after the
        padding are unchanged. Name text (trust prefixes, city renames,
        added/dropped suffixes) is deliberately NOT part of this key — name
        drift is exactly what breaks naive name-equality grouping.
    """
    for frag in RECODED_COLLEGES:
        if frag in college_name:
            return f"NAME::{frag}"
    return "CODE::" + college_code.lstrip("0")


# ---------------------------------------------------------------------------
# Seat-eligibility layer (Phase 4)
#
# MHT-CET CAP splits seats into Home University (H), Other-Than-Home (O) and
# State Level (S). Whether a given college offers a student an H seat or an O
# seat depends ENTIRELY on whether the student's home university == the
# college's university. So the engine must, per college, pick the H or O
# category variant. These maps are the single source of truth for that.
# ---------------------------------------------------------------------------

# Dirty district strings (uppercase, sub-districts, talukas) -> canonical
# district name as it appears in the home_university_map table. Only entries
# that actually occur in college_details.district are listed; extend as needed.
DISTRICT_ALIASES = {
    # case / spelling
    "PUNE": "Pune", "MUMBAI": "Mumbai", "MUMBAI CITY": "Mumbai City",
    "MUMBAI SUBURBAN": "Mumbai Suburban", "THANE": "Thane", "NASHIK": "Nashik",
    "NAGPUR": "Nagpur", "KOLHAPUR": "Kolhapur", "SOLAPUR": "Solapur",
    "SANGLI": "Sangli", "SATARA": "Satara", "AHMEDNAGAR": "Ahmednagar",
    "AMRAVATI": "Amravati", "AKOLA": "Akola", "YAVATMAL": "Yavatmal",
    "BULDHANA": "Buldhana", "WASHIM": "Washim", "NANDED": "Nanded",
    "LATUR": "Latur", "OSMANABAD": "Dharashiv", "DHARASHIV": "Dharashiv",
    "BEED": "Beed", "JALNA": "Jalna",
    # Aurangabad -> Chhatrapati Sambhajinagar, official Maharashtra government
    # rename (Gazette notification, 2023) — same decision that renamed Osmanabad
    # to Dharashiv above. All spelling variants normalize to the current name.
    "AURANGABAD": "Chhatrapati Sambhajinagar",
    "CHHATRAPATI SAMBHAJINAGAR": "Chhatrapati Sambhajinagar",
    "SAMBHAJINAGAR": "Chhatrapati Sambhajinagar",
    "SAMBHAJI NAGAR": "Chhatrapati Sambhajinagar",
    "CHHATRAPATI SAMBHAJI NAGAR": "Chhatrapati Sambhajinagar",
    "PARBHANI": "Parbhani", "HINGOLI": "Hingoli",
    "JALGAON": "Jalgaon", "DHULE": "Dhule", "NANDURBAR": "Nandurbar",
    "WARDHA": "Wardha", "CHANDRAPUR": "Chandrapur", "GADCHIROLI": "Gadchiroli",
    "GONDIA": "Gondia", "BHANDARA": "Bhandara", "RAIGAD": "Raigad",
    "RAIGARH": "Raigad", "RATNAGIRI": "Ratnagiri", "SINDHUDURG": "Sindhudurg",
    "PALGHAR": "Palghar",
    # sub-districts / talukas -> parent district
    "Pune City Subdistrict": "Pune", "Haveli Subdistrict": "Pune",
    "Mulshi Subdistrict": "Pune", "Mawal": "Pune", "Kusgaon, Lonavala": "Pune",
    "Thane Subdistrict": "Thane", "Nagpur Urban Taluka": "Nagpur",
    "Nashik Subdistrict": "Nashik", "Rahta": "Ahmednagar",
    "Karvir": "Kolhapur", "Walwa": "Sangli", "Solapur North": "Solapur",
    "Pandharpur": "Solapur", "Raigarh": "Raigad",
    "Nagar Subdistrict": "Ahmednagar", "Chandrapur Taluka": "Chandrapur",
    "Karjat Taluka": "Raigad", "Malkapur": "Buldhana", "Devrukh": "Ratnagiri",
    "Gadhinglaj": "Kolhapur", "Hingna": "Nagpur",
}

# City -> canonical district, used to backfill colleges whose district is blank
# (colleges.city is 379/379 populated). Only majors needed for engineering hubs.
CITY_TO_DISTRICT = {
    "Pune": "Pune", "Pimpri": "Pune", "Chinchwad": "Pune", "Pimpri-Chinchwad": "Pune",
    "Lonavala": "Pune", "Lonavla": "Pune", "Talegaon": "Pune", "Akurdi": "Pune",
    "Mumbai": "Mumbai", "Navi Mumbai": "Thane", "Thane": "Thane", "Kalyan": "Thane",
    "Panvel": "Raigad", "Nerul": "Thane", "Vashi": "Thane", "Powai": "Mumbai",
    "Nagpur": "Nagpur", "Nashik": "Nashik", "Nasik": "Nashik",
    "Kolhapur": "Kolhapur", "Sangli": "Sangli", "Miraj": "Sangli", "Satara": "Satara",
    "Solapur": "Solapur", "Pandharpur": "Solapur", "Ahmednagar": "Ahmednagar",
    "Amravati": "Amravati", "Akola": "Akola", "Yavatmal": "Yavatmal",
    "Buldhana": "Buldhana", "Washim": "Washim", "Nanded": "Nanded", "Latur": "Latur",
    # Aurangabad/Osmanabad are the pre-2023 names of Chhatrapati Sambhajinagar/
    # Dharashiv (official Maharashtra government rename) — both old and new
    # spellings map to the CURRENT name, never the retired one.
    "Aurangabad": "Chhatrapati Sambhajinagar",
    "Chhatrapati Sambhajinagar": "Chhatrapati Sambhajinagar",
    "Sambhaji Nagar": "Chhatrapati Sambhajinagar",
    "Sambhajinagar": "Chhatrapati Sambhajinagar",
    "Jalna": "Jalna", "Beed": "Beed",
    "Osmanabad": "Dharashiv", "Dharashiv": "Dharashiv", "Parbhani": "Parbhani",
    "Jalgaon": "Jalgaon", "Dhule": "Dhule", "Nandurbar": "Nandurbar",
    "Wardha": "Wardha", "Chandrapur": "Chandrapur", "Gondia": "Gondia",
    "Bhandara": "Bhandara", "Gadchiroli": "Gadchiroli", "Ratnagiri": "Ratnagiri",
    "Sindhudurg": "Sindhudurg", "Karad": "Satara", "Ichalkaranji": "Kolhapur",
    "Shegaon": "Buldhana", "Shirpur": "Dhule", "Loni": "Ahmednagar",
    "Sangamner": "Ahmednagar", "Baramati": "Pune", "Wagholi": "Pune",
    "Badlapur": "Thane", "Jaysingpur": "Kolhapur", "Pusad": "Yavatmal",
    "Bhor": "Pune", "Raigad": "Raigad", "Palghar": "Palghar",
    "Gadhinglaj": "Kolhapur", "Kanhor": "Thane", "Tala": "Raigad",
    "Kaman": "Palghar", "Karjat": "Raigad", "Devrukh": "Ratnagiri",
}


def normalize_district(district, city=None):
    """
    Map a raw college district (and optional city fallback) to a canonical
    district name that exists in home_university_map. Returns None if it can't
    be resolved — caller must treat None explicitly, never silently.
    """
    if district:
        d = district.strip()
        if d in DISTRICT_ALIASES:
            return DISTRICT_ALIASES[d]
        # Title-case form might already be canonical
        title = d.title()
        if title in CITY_TO_DISTRICT:  # e.g. district stored a city name
            return CITY_TO_DISTRICT[title]
        # Accept as-is if it's already a clean district token
        if d and d.upper() != d.lower():
            return title if title not in ("",) else None
    if city:
        return CITY_TO_DISTRICT.get(city.strip().title())
    return None


# Base category -> (Home variant, Other variant, State variant).
# State-only categories map to (None, None, state_code): eligible everywhere.
BASE_CATEGORY_VARIANTS = {
    "GOPEN":  ("GOPENH",  "GOPENO",  "GOPENS"),
    "GSC":    ("GSCH",    "GSCO",    "GSCS"),
    "GST":    ("GSTH",    "GSTO",    "GSTS"),
    "GOBC":   ("GOBCH",   "GOBCO",   "GOBCS"),
    "GVJ":    ("GVJH",    "GVJO",    "GVJS"),
    "GNT1":   ("GNT1H",   "GNT1O",   "GNT1S"),
    "GNT2":   ("GNT2H",   "GNT2O",   "GNT2S"),
    "GNT3":   ("GNT3H",   "GNT3O",   "GNT3S"),
    "GSEBC":  ("GSEBCH",  "GSEBCO",  "GSEBCS"),
    "LOPEN":  ("LOPENH",  "LOPENO",  "LOPENS"),
    "LSC":    ("LSCH",    "LSCO",    "LSCS"),
    "LST":    ("LSTH",    "LSTO",    "LSTS"),
    "LOBC":   ("LOBCH",   "LOBCO",   "LOBCS"),
    "LVJ":    ("LVJH",    "LVJO",    "LVJS"),
    "LNT1":   ("LNT1H",   "LNT1O",   "LNT1S"),
    "LNT2":   ("LNT2H",   "LNT2O",   "LNT2S"),
    "LNT3":   ("LNT3H",   "LNT3O",   "LNT3S"),
    "LSEBC":  ("LSEBCH",  "LSEBCO",  "LSEBCS"),
    # State-only (no H/O split) — eligible at every college
    "EWS":      (None, None, "EWS"),
    "TFWS":     (None, None, "TFWS"),
    "DEFOPEN":  (None, None, "DEFOPENS"),
    "ORPHAN":   (None, None, "ORPHAN"),
    "PWDOPEN":  ("PWDOPENH", None, "PWDOPENS"),
    "PWDOBC":   ("PWDOBCH",  None, "PWDOBCS"),
    "PWDSC":    ("PWDSCH",   None, "PWDSCS"),
    "PWDSEBC":  ("PWDSEBCH", None, "PWDSEBCS"),
}

# SAFE / PROBABLE / REACH thresholds on margin = student_pct - predicted_close.
# Locked in phase4_design.md Step 2.4 — do not change mid-build.
# Used as the REACH-window fallback when a predicted_low/predicted_high interval
# is unavailable for a row (see compute_interval_offsets / _band in preference_engine.py).
BAND_SAFE_MIN    = 3.0    # margin >= +3.0 and confidence != low
BAND_PROBABLE_MIN = -1.0  # -1.0 <= margin < 3.0
BAND_REACH_MIN   = -4.0   # -4.0 <= margin < -1.0 ; below -4.0 excluded

# Backtest-derived: above this max-min spread in the yearly closings, the
# carry-forward error grows past ~11 MAE and the prediction must be low
# confidence (never SAFE) and "volatile" for interval-offset bucketing.
# Single source of truth — generate_predictions.py imports this, never redefines it.
VOLATILITY_SPREAD_MAX = 10.0


def resolve_seat_category(base_category, student_univ, college_univ):
    """
    Given the student's BASE category and whether the student is Home or Other
    relative to a specific college, return the ordered list of CAP category
    codes to evaluate that college against (most-specific first).

    Returns [] if base_category is unknown (caller must handle, never guess).
    """
    variants = BASE_CATEGORY_VARIANTS.get(base_category.upper())
    if not variants:
        return []
    home_v, other_v, state_v = variants
    is_home = (student_univ is not None
               and college_univ is not None
               and student_univ == college_univ)
    chain = []
    if is_home and home_v:
        chain.append(home_v)
    elif not is_home and other_v:
        chain.append(other_v)
    if state_v and state_v not in chain:
        chain.append(state_v)
    return chain


# ---------------------------------------------------------------------------
# Impossible-percentile detector (source-PDF glitch gate)
#
# CET Cell's own PDFs contain rows whose printed percentile is impossible for
# the printed merit number — e.g. 2024 R1 ICT TFWS: merit 1102 (top ~0.5% of
# the state list) printed as "(0.0000000)". Verified against the source PDF:
# the glitch is IN the official PDF, not our parser. 65 such rows existed in
# the 2023-2025 data, all TFWS. Left in, MIN() aggregation makes 0.0 the
# "closing cutoff" and the engine calls a ~99.9-percentile seat SAFE for anyone.
#
# Detection is a within-year monotonicity test, because percentile-vs-merit is
# NOT a fixed curve across years (2023's list bottom sits at merit ~143k with
# legitimate 0.0x percentiles): a row is impossible only if the MEDIAN
# percentile of the ~500 rows ranked immediately WORSE (higher merit_no) that
# year is far ABOVE its own printed percentile. Genuine bottom-of-list rows
# pass (their worse-ranked neighbours are also ~0); glitch rows fail by 30+ pts.
# Tuned on the full 2023-2025 DB: flags exactly the 65 glitch rows, 0 false
# positives on 235k rows.
# ---------------------------------------------------------------------------
MERIT_GATE_WINDOW = 500   # worse-ranked rows to compare against
MERIT_GATE_MIN_WINDOW = 50    # need at least this many to judge
MERIT_GATE_MAX_DEFICIT = 30.0  # flag if median(worse) - own pct exceeds this


def find_impossible_percentile_keys(rows):
    """
    rows: iterable of (key, year, percentile, merit_no) for MH (is_all_india=0)
    cutoff rows. Returns the set of keys whose printed percentile is impossibly
    low for their merit number (see module comment). Rows with merit_no None
    are never flagged.
    """
    import statistics

    by_year = {}
    for key, year, pct, merit in rows:
        if merit is None or pct is None:
            continue
        by_year.setdefault(year, []).append((merit, pct, key))

    flagged = set()
    for year_rows in by_year.values():
        year_rows.sort()  # by merit ascending (best rank first)
        pcts = [p for _, p, _ in year_rows]
        for i, (_, pct, key) in enumerate(year_rows):
            window = pcts[i + 1: i + 1 + MERIT_GATE_WINDOW]
            if len(window) < MERIT_GATE_MIN_WINDOW:
                continue
            if statistics.median(window) - pct > MERIT_GATE_MAX_DEFICIT:
                flagged.add(key)
    return flagged


# ---------------------------------------------------------------------------
# predictions_2026 schema — SINGLE SOURCE OF TRUTH.
#
# This table used to be CREATE-d independently in BOTH setup_college_profiles.py
# and generate_predictions.py. The two definitions drifted (one gained a
# canonical_code column, the other didn't), which crashed prediction generation.
# Defining it once here and calling ensure_predictions_table() from both scripts
# makes drift impossible. NEVER inline this CREATE TABLE anywhere else.
# ---------------------------------------------------------------------------
def ensure_predictions_table(conn):
    """
    Create predictions_2026 if absent, migrating away a stale pre-canonical_code
    schema (the table is fully regenerable, so drop & recreate rather than ALTER).
    Safe to call repeatedly. Returns True if an old table was dropped.
    """
    dropped = False
    row = conn.execute(
        "SELECT sql FROM sqlite_master WHERE type='table' AND name='predictions_2026'"
    ).fetchone()
    if row and ("canonical_code" not in row[0] or "predicted_low" not in row[0]):
        conn.execute("DROP TABLE predictions_2026")
        dropped = True

    conn.execute("""
        CREATE TABLE IF NOT EXISTS predictions_2026 (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            canonical_code  TEXT NOT NULL,
            college_name    TEXT NOT NULL,
            branch_name     TEXT NOT NULL,
            college_code    TEXT NOT NULL,
            branch_code     TEXT NOT NULL,
            category        TEXT NOT NULL,
            round           INTEGER NOT NULL,
            predicted_pct   REAL NOT NULL,
            predicted_low   REAL,
            predicted_high  REAL,
            trend_slope     REAL,
            confidence      TEXT NOT NULL,
            years_used      INTEGER NOT NULL,
            generated_at    TEXT NOT NULL,
            UNIQUE(canonical_code, category, round)
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_pred_lookup ON predictions_2026(category, round)")
    return dropped


# ---------------------------------------------------------------------------
# Calibrated interval predictions (Phase 5 roadmap item B1)
#
# The carry-forward point estimate is at its accuracy ceiling (backtest MAE
# ~8.3; see scripts/backtest_predictions.py). The honesty gain left on the
# table is a calibrated uncertainty band: predicted_low/predicted_high on
# predictions_2026, derived EMPIRICALLY from the same train/test backtest
# split, stratified by tier (closing-percentile level) x volatility (history
# spread). NEVER hardcode the offset numbers — always recompute from the DB
# via compute_interval_offsets() so the interval tracks whatever data is
# currently loaded (e.g. widens/narrows once Wayback history (A1) lands).
# ---------------------------------------------------------------------------
MIN_INTERVAL_BUCKET_N = 30  # below this, fall back to the coarser tier-only (then global) bucket


def tier_of_pct(pct):
    """Bucket a closing percentile into the tier used for interval calibration."""
    if pct >= 97:
        return "elite"
    if pct >= 90:
        return "high"
    if pct >= 70:
        return "mid"
    return "low"


def _p10_p50_p90(errs):
    if not errs:
        return (0.0, 0.0, 0.0)
    if len(errs) < 2:
        return (errs[0], errs[0], errs[0])
    q = statistics.quantiles(errs, n=10, method="inclusive")
    return (q[0], statistics.median(errs), q[8])


def compute_interval_offsets(conn):
    """
    Empirically fit signed error offsets (actual - predicted) for the carry-forward
    model, stratified by (tier, volatility), using the same fit-earlier/score-latest
    method as backtest_predictions.py. Returns {(tier, volatility): (p10, p50, p90)}.

    tier        = tier_of_pct() of the carry-forward prediction (train years' latest).
    volatility  = "stable" if the train-year spread is <= VOLATILITY_SPREAD_MAX else
                  "volatile" — the same reliability test generate_predictions.py uses.

    predicted_low  = clamp(predicted + p10, 0, 100)
    predicted_high = clamp(predicted + p90, 0, 100)

    Sparse cells fall back to the tier-level (volatility-blind) distribution, then to
    the global distribution, so every (tier, volatility) combination always resolves
    to *some* interval rather than a missing one.
    """
    rows = conn.execute("""
        SELECT col.college_name, b.branch_name, cu.branch_code, cu.category,
               cu.round, cu.year, MIN(cu.percentile)
        FROM cutoffs cu
        JOIN branches b   ON cu.branch_code  = b.branch_code
        JOIN colleges col ON b.college_code  = col.college_code
        WHERE cu.is_all_india = 0 AND cu.exam_type LIKE 'MHT-CET%'
        GROUP BY cu.branch_code, cu.category, cu.round, cu.year
    """).fetchall()

    groups = {}
    for cname, bname, bc, cat, rnd, yr, pct in rows:
        key = (canonical_branch_key(cname, bname, bc), cat, rnd)
        g = groups.setdefault(key, {})
        if yr not in g or pct < g[yr]:
            g[yr] = pct

    years = sorted({y for g in groups.values() for y in g})
    if len(years) < 2:
        return {}
    train_years, test_year = years[:-1], years[-1]

    tiers = ("elite", "high", "mid", "low")
    vols = ("stable", "volatile")
    cell_errs = {(t, v): [] for t in tiers for v in vols}
    tier_errs = {t: [] for t in tiers}
    all_errs = []

    for g in groups.values():
        if test_year not in g:
            continue
        train_pairs = sorted((y, g[y]) for y in train_years if y in g)
        if not train_pairs:
            continue
        predicted = train_pairs[-1][1]
        vals = [p for _, p in train_pairs]
        spread = (max(vals) - min(vals)) if len(vals) > 1 else 0.0
        vol = "stable" if spread <= VOLATILITY_SPREAD_MAX else "volatile"
        tier = tier_of_pct(predicted)
        err = g[test_year] - predicted

        cell_errs[(tier, vol)].append(err)
        tier_errs[tier].append(err)
        all_errs.append(err)

    global_offsets = _p10_p50_p90(all_errs)
    offsets = {}
    for tier in tiers:
        tier_fallback = (_p10_p50_p90(tier_errs[tier])
                          if len(tier_errs[tier]) >= MIN_INTERVAL_BUCKET_N else global_offsets)
        for vol in vols:
            errs = cell_errs[(tier, vol)]
            if len(errs) >= MIN_INTERVAL_BUCKET_N:
                offsets[(tier, vol)] = _p10_p50_p90(errs)
            else:
                offsets[(tier, vol)] = tier_fallback
    return offsets
