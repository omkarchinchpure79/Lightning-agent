"""
engine_adapter.py  (Phase 5 — the contract boundary between engine and UI)

A thin, UI-framework-agnostic bridge over the Phase 4 engine. The Streamlit app
talks ONLY to this module, never to the engine directly. Responsibilities:

  1. Make the engine importable & runnable from ANY working directory (the engine
     modules use a relative DB path; we pin them to an absolute path here).
  2. Map counsellor-friendly inputs (category label) -> engine base_category code.
  3. Provide dropdown source lists (districts, categories, branch keywords).
  4. Wrap the four engine calls in plain functions returning the engine dicts
     unchanged — so the data contract the UI sees is exactly Phase 4's output.

No Streamlit import here: this stays testable as pure Python (and IS unit-tested).
"""

import os
import sqlite3
import sys

# --- 1. Make engine importable from anywhere, with an absolute DB path ---------
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_SCRIPTS = os.path.join(_PROJECT_ROOT, "scripts")
# EDUPATH_DB_PATH lets a deployment keep the DB on a persistent disk outside
# the repo (e.g. /data/edupath.db); falls back to the in-repo default.
_DB = os.environ.get("EDUPATH_DB_PATH") or os.path.join(_PROJECT_ROOT, "db", "edupath.db")
if _SCRIPTS not in sys.path:
    sys.path.insert(0, _SCRIPTS)

import preference_engine as _pe          # noqa: E402
import cap_round_strategy as _rs          # noqa: E402
import college_card_api as _cc            # noqa: E402
import fee_calculator as _fc              # noqa: E402
import dse_engine as _dse                 # noqa: E402
from constants import BASE_CATEGORY_VARIANTS  # noqa: E402  (single source of truth)

# Pin every engine module's relative DB_PATH to the absolute file, so the app
# works regardless of the directory `streamlit run` is launched from.
for _m in (_pe, _rs, _cc, _fc, _dse):
    _m.DB_PATH = _DB


# --- 2. Counsellor category labels -> engine base_category --------------------
# One explicit dropdown, no gender/eligibility ambiguity: each label is exactly
# one seat pool the engine understands. Grouped for readability in the UI.
CATEGORY_OPTIONS = [
    ("General — Open",        "GOPEN"),
    ("General — SC",          "GSC"),
    ("General — ST",          "GST"),
    ("General — OBC",         "GOBC"),
    ("General — VJ/DT",       "GVJ"),
    ("General — NT-B (NT1)",  "GNT1"),
    ("General — NT-C (NT2)",  "GNT2"),
    ("General — NT-D (NT3)",  "GNT3"),
    ("General — SEBC",        "GSEBC"),
    ("Ladies — Open",         "LOPEN"),
    ("Ladies — SC",           "LSC"),
    ("Ladies — ST",           "LST"),
    ("Ladies — OBC",          "LOBC"),
    ("Ladies — VJ/DT",        "LVJ"),
    ("Ladies — NT-B (NT1)",   "LNT1"),
    ("Ladies — NT-C (NT2)",   "LNT2"),
    ("Ladies — NT-D (NT3)",   "LNT3"),
    ("Ladies — SEBC",         "LSEBC"),
    ("EWS",                   "EWS"),
    ("TFWS (Tuition Fee Waiver)", "TFWS"),
    ("Defence — Open",        "DEFOPEN"),
    ("Orphan",                "ORPHAN"),
    ("PwD — Open",            "PWDOPEN"),
    ("PwD — OBC",             "PWDOBC"),
    ("PwD — SC",              "PWDSC"),
    ("PwD — SEBC",            "PWDSEBC"),
]
_LABEL_TO_CODE = {label: code for label, code in CATEGORY_OPTIONS}


def category_labels():
    return [label for label, _ in CATEGORY_OPTIONS]


def category_code(label):
    """Friendly label -> base_category code. Falls back to the label itself if
    the caller already passed a code (so the adapter is forgiving)."""
    return _LABEL_TO_CODE.get(label, label)


# --- 3. Dropdown source lists (from the live DB) -----------------------------
# UI sentinel for students whose home district isn't a Maharashtra district the
# engine can resolve (out-of-state / All-India candidates). Selecting it runs the
# engine WITHOUT home-district resolution (district=None), which surfaces the
# district_unresolved warning. Kept here (the bridge), not in the UI layer.
DISTRICT_OTHER = "Other / Not listed"


def list_districts():
    """Canonical districts the engine can resolve to a home university."""
    conn = sqlite3.connect(_DB)
    try:
        rows = [r[0] for r in conn.execute(
            "SELECT DISTINCT district FROM home_university_map ORDER BY district")]
    finally:
        conn.close()
    # Collapse the three Mumbai variants (all -> University of Mumbai) into one.
    cleaned, seen_mumbai = [], False
    for d in rows:
        if d.startswith("Mumbai"):
            if seen_mumbai:
                continue
            cleaned.append("Mumbai")
            seen_mumbai = True
        else:
            cleaned.append(d)
    return cleaned


def district_options():
    """District dropdown choices: resolvable districts + the 'Other / Not listed' sentinel."""
    return list_districts() + [DISTRICT_OTHER]


def resolve_district_input(choice):
    """Map a dropdown choice to the engine arg: None for the 'Other' sentinel."""
    return None if choice == DISTRICT_OTHER else choice


# Common branch keywords for the preference filter (substring match in engine).
BRANCH_KEYWORDS = [
    "Computer", "Information Technology", "Artificial Intelligence", "Data Science",
    "Electronics", "Telecommunication", "Electrical", "Mechanical", "Civil",
    "Chemical", "Instrumentation", "Robotics", "Mechatronics", "Biomedical",
    "Production", "Automobile", "Metallurgy", "Aeronautical",
]


def list_branch_keywords():
    return list(BRANCH_KEYWORDS)


# --- 4. Engine call wrappers (return engine dicts unchanged) ------------------
def _annotate_seat_data(result, base_category):
    """
    Tag each result row with how its prediction's CAP category relates to what the
    student should ideally get, so the UI can show an honest seat-data line (Fix C2):
      - "exact"      : category_used IS the student's home/other category for that college
      - "fallback"   : no home/other cutoff existed, so a State-level (…S) cutoff was used
      - "state_only" : the base category has no home/other split (EWS/TFWS/PwD/…)
    Adds row["seat_data_status"] and row["expected_category"]. Pure post-processing
    of the engine output + a constants lookup; the engine is NOT re-called.
    """
    variants = BASE_CATEGORY_VARIANTS.get(base_category)
    if not variants:
        return result
    home_v, other_v, state_v = variants
    state_only = home_v is None and other_v is None
    student_univ = result.get("student_university")

    # One batched college_code -> university_code lookup (to decide Home vs Other).
    univ = {}
    if not state_only:
        codes = {r["college_code"] for b in ("safe", "probable", "reach")
                 for r in result[b]}
        if codes:
            conn = sqlite3.connect(_DB)
            try:
                qs = ",".join("?" * len(codes))
                univ = dict(conn.execute(
                    f"SELECT college_code, university_code FROM college_details "
                    f"WHERE college_code IN ({qs})", list(codes)).fetchall())
            finally:
                conn.close()

    for b in ("safe", "probable", "reach"):
        for r in result[b]:
            if state_only:
                r["seat_data_status"] = "state_only"
                r["expected_category"] = state_v
                continue
            is_home = (student_univ is not None
                       and univ.get(r["college_code"]) == student_univ)
            expected = home_v if is_home else other_v
            r["expected_category"] = expected
            r["seat_data_status"] = ("exact" if r["category_used"] == expected
                                     else "fallback")
    return result


# --- Reserved-pool eligibility (Fix C1) ---------------------------------------
# student_profiles collects tfws_eligible / defense_status / pwd_status /
# orphan_status / family_income_bracket, but until now nothing downstream ever
# queried those pools — a TFWS-eligible student saw only their base category,
# missing seats that are often the best value (tuition waived). When a flag is
# set, we re-run the engine for that pool's base category and merge its rows
# into the SAME bands, tagged with which pool they came from.

# pwd_status is a disability flag, not a category choice — the CAP PWD variant
# is the student's OWN base category with a PWD prefix. Only these four base
# categories have a PWD variant defined in BASE_CATEGORY_VARIANTS; students in
# any other base category have no PWD pool to add (never guessed).
_PWD_VARIANT_BY_BASE = {
    "GOPEN": "PWDOPEN", "GOBC": "PWDOBC", "GSC": "PWDSC", "GSEBC": "PWDSEBC",
}

# EWS (Economically Weaker Section) is a reservation ONLY for candidates in the
# Open/General category — a student already in a reserved category (SC/ST/OBC/
# SEBC/VJ/NT) is legally NOT EWS-eligible. It is added ONLY when the counsellor
# explicitly ticks ews_eligible AND the base category is open. Historically it
# was auto-added from a low family_income_bracket, which surfaced a phantom "EWS
# pool" on students who never selected it (e.g. an SEBC student) — a real glitch
# the counsellor flagged (2026-07-05). Income alone never triggers EWS now.
_EWS_ELIGIBLE_BASES = {"GOPEN", "LOPEN"}


def _eligible_pools(base_category, tfws_eligible, defense_status, pwd_status,
                     orphan_status, ews_eligible):
    """(pool_label, base_category) pairs this student should ALSO be shown,
    beyond their primary category. Never duplicates the primary category itself."""
    pools = []
    if tfws_eligible:
        pools.append(("TFWS", "TFWS"))
    if defense_status:
        pools.append(("Defence", "DEFOPEN"))
    if orphan_status:
        pools.append(("Orphan", "ORPHAN"))
    if pwd_status:
        pwd_cat = _PWD_VARIANT_BY_BASE.get(base_category.upper())
        if pwd_cat:
            pools.append(("PwD", pwd_cat))
    if ews_eligible and base_category.upper() in _EWS_ELIGIBLE_BASES:
        pools.append(("EWS", "EWS"))
    return [(label, cat) for label, cat in pools if cat != base_category.upper()]


def _merge_pool(primary, extra, pool_label):
    """Append one extra pool's rows as DISTINCT selectable entries, tagged
    seat_pool=pool_label.

    A pool seat (e.g. TFWS's separate ~6-seat quota) is a genuinely different
    seat a student opts into — not an alternate view of the general seat — so it
    is NOT de-duplicated against the primary-category row for the same branch.
    The counsellor sees both the general entry and the TFWS entry for a college
    and can shortlist either independently (counsellor request 2026-07-05).
    Distinct identity for the frontend/shortlist is canonical_code + seat_pool
    (set as entry_key in preference_list)."""
    if "error" in extra:
        return
    for band in ("safe", "probable", "reach"):
        for row in extra[band]:
            row["seat_pool"] = pool_label
            primary[band].append(row)
            primary["counts"][band] += 1


def preference_list(percentile, category_label, home_district,
                    branch_preferences=None, fee_budget=None,
                    round_num=1, top_per_band=None, preferred_locations=None,
                    tfws_eligible=False, defense_status=False, pwd_status=False,
                    orphan_status=False, family_income_bracket=None,
                    ews_eligible=False):
    base_category = category_code(category_label)
    out = _pe.compute_preference_list(
        percentile=percentile,
        base_category=base_category,
        home_district=home_district,
        branch_preferences=branch_preferences or None,
        fee_budget=fee_budget,
        round_num=round_num,
        top_per_band=None,  # truncate AFTER merging extra pools, not before
        preferred_locations=preferred_locations or None,
    )
    if "error" in out:
        return out
    out = _annotate_seat_data(out, base_category)
    for band in ("safe", "probable", "reach"):
        for row in out[band]:
            row["seat_pool"] = None

    for pool_label, pool_category in _eligible_pools(
        base_category, tfws_eligible, defense_status, pwd_status,
        orphan_status, ews_eligible
    ):
        extra = _pe.compute_preference_list(
            percentile=percentile,
            base_category=pool_category,
            home_district=home_district,
            branch_preferences=branch_preferences or None,
            fee_budget=fee_budget,
            round_num=round_num,
            top_per_band=None,
            preferred_locations=preferred_locations or None,
        )
        if "error" not in extra:
            extra = _annotate_seat_data(extra, pool_category)
        _merge_pool(out, extra, pool_label)

    # Distinct selectable identity: a pool seat (TFWS/EWS/…) shares canonical_code
    # with the general seat for the same branch but is a different entry, so the
    # frontend keys, selection, and shortlist de-dup on entry_key, not canonical_code.
    for band in ("safe", "probable", "reach"):
        for row in out[band]:
            pool = row.get("seat_pool")
            row["entry_key"] = f"{row['canonical_code']}::{pool}" if pool else row["canonical_code"]

    # Re-sort by desirability (same key preference_engine.py uses): merging appends
    # extra-pool rows out of order, and callers rely on array order for "top N"
    # display slices even when top_per_band is None (unbounded).
    for band in ("safe", "probable", "reach"):
        out[band].sort(key=lambda r: (-r["predicted_close"], -(r["college_score"] or 0)))
        if top_per_band:
            out[band] = out[band][:top_per_band]
    return out


def dse_preference_list(diploma_pct, category_label, branch_preferences=None,
                        fee_budget=None, round_num=1, top_per_band=None,
                        preferred_locations=None):
    """DSE (diploma lateral entry) twin of preference_list.

    No reserved-pool merging (no TFWS in DSE; PWD/DEF/ORPHAN are plain
    categories selectable as the base category) and no seat-data fallback
    annotation (DSE has no H/O/S variants, so every match is exact by
    construction). entry_key == canonical_code: one seat pool per branch."""
    base_category = category_code(category_label)
    out = _dse.compute_dse_preference_list(
        diploma_pct=diploma_pct,
        base_category=base_category,
        branch_preferences=branch_preferences or None,
        fee_budget=fee_budget,
        round_num=round_num,
        top_per_band=top_per_band,
        preferred_locations=preferred_locations or None,
    )
    if "error" in out:
        return out
    for band in ("safe", "probable", "reach"):
        for row in out[band]:
            row["seat_pool"] = None
            row["entry_key"] = row["canonical_code"]
            row["seat_data_status"] = "exact"
            row["expected_category"] = row["category_used"]
    return out


def round_strategy(percentile, category_label, home_district, branch_preferences=None):
    return _rs.get_round_strategy(
        percentile, category_code(category_label), home_district,
        branch_preferences or None)


def college_profile(college_code):
    return _cc.get_college_profile(college_code)


def fee_for(college_code, category_label):
    conn = sqlite3.connect(_DB)
    try:
        return _fc.compute_fee(conn, college_code, category_code(category_label))
    finally:
        conn.close()


def db_path():
    return _DB
