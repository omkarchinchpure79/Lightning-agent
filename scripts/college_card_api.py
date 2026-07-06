"""
college_card_api.py  (Phase 4 — Priority 3)

One call -> everything the frontend needs to render a college card:
  get_college_profile(college_code) -> dict with
    identity, accreditation, location/contact, facilities, placements,
    fee breakdown by category, quality score + subset breakdown, images,
    and per-branch cutoff trends (2023 -> 2024 -> 2025 -> 2026 prediction).

Accepts a 4- or 5-digit code and aggregates across ALL paired codes for the
same physical college (CET Cell re-codes colleges across years). Fail-soft:
missing fields come back as None, never crash.
"""

import argparse
import json
import os
import sqlite3

from constants import BRANCH_NAME_ALIASES, OPEN_CATEGORIES, canonical_branch_key, canonical_college_key
from fee_calculator import compute_fee

DB_PATH = "db/edupath.db"
FEE_CATEGORIES = ["GOPEN", "GOBC", "GSC", "TFWS"]
# Representative categories for the cutoff trend line (open seats).
TREND_CATEGORIES = OPEN_CATEGORIES
# Base URL the frontend can reach the API's own static image mount at.
API_PUBLIC_BASE = os.environ.get("API_PUBLIC_BASE", "http://localhost:8000")


def _paired_codes(conn, college_code):
    """
    All college_codes identifying the same physical college (4-/5-digit code
    variants, and codes that persisted through a name/district change — e.g.
    Aurangabad -> Chhatrapati Sambhajinagar). Grouped by canonical_college_key,
    NOT by exact college_name match: real PDFs don't repeat identical name text
    year to year, so name-equality silently missed pairs like this.
    """
    row = conn.execute("SELECT college_name FROM colleges WHERE college_code=?",
                       (college_code,)).fetchone()
    if not row:
        return [], None
    name = row[0]
    key = canonical_college_key(college_code, name)
    codes = [r[0] for r in conn.execute("SELECT college_code, college_name FROM colleges")
             if canonical_college_key(r[0], r[1]) == key]
    return codes, name


def _profile(conn, college_code):
    cols = ("university_code, affiliated_university, naac_grade, naac_score, "
            "nirf_rank, nba_branches, is_autonomous, year_established, "
            "institution_type, management_name, campus_area_acres, "
            "has_hostel_boys, has_hostel_girls, has_sports, has_wifi, "
            "placement_pct, avg_package_lpa, highest_package_lpa, top_recruiters, "
            "placement_reliable, address, district, website_url, email, phone, "
            "latitude, longitude, google_maps_url, image_metadata, local_image_paths")
    row = conn.execute(
        f"SELECT {cols} FROM college_details WHERE college_code=?",
        (college_code,)).fetchone()
    if not row:
        # Try any paired code that has details
        for code in _paired_codes(conn, college_code)[0]:
            row = conn.execute(
                f"SELECT {cols} FROM college_details WHERE college_code=?",
                (code,)).fetchone()
            if row:
                break
    keys = cols.replace(" ", "").split(",")
    return dict(zip(keys, row)) if row else {k: None for k in cols.replace(" ", "").split(",")}


def _scores(conn, codes):
    """Overall score (from colleges) + subset breakdown (best non-null per subset)."""
    placeholders = ",".join("?" * len(codes))
    overall = conn.execute(
        f"SELECT MAX(score), MAX(completeness) FROM colleges WHERE college_code IN ({placeholders})",
        codes).fetchone()
    subsets = {}
    for name, score in conn.execute(
        f"SELECT subset_name, score FROM college_subset_scores "
        f"WHERE college_code IN ({placeholders})", codes):
        if name not in subsets or score > subsets[name]:
            subsets[name] = score
    return {"overall": overall[0] if overall else None,
            "completeness": overall[1] if overall else None,
            "subsets": subsets}


def _cutoff_trends(conn, codes):
    """
    Per-branch closing percentile across years for the representative open
    categories, plus the 2026 prediction. Returns list sorted by 2025 close desc.
    """
    placeholders = ",".join("?" * len(codes))
    tph = ",".join("?" * len(TREND_CATEGORIES))

    # Historical 2023-2025: MIN percentile per branch_name + year (open cats).
    # Round 1 only — the 2026 column is a ROUND-1 prediction, so the history
    # must be round-1 closes too, or the trend line lies (a later-round close
    # is always lower and makes 2026 look like a spurious rise).
    hist = {}
    for bname, year, pct in conn.execute(f"""
        SELECT b.branch_name, cu.year, MIN(cu.percentile)
        FROM cutoffs cu
        JOIN branches b ON cu.branch_code = b.branch_code
        WHERE b.college_code IN ({placeholders})
          AND cu.category IN ({tph})
          AND cu.round = 1
          AND cu.is_all_india = 0 AND cu.exam_type LIKE 'MHT-CET%'
        GROUP BY b.branch_name, cu.year
    """, codes + list(TREND_CATEGORIES)):
        # Renamed branches (COEP CSE 2023->2024) must land on ONE trend row.
        bname = BRANCH_NAME_ALIASES.get(bname, bname)
        if year in hist.get(bname, {}):
            pct = min(pct, hist[bname][year])
        hist.setdefault(bname, {})[year] = round(pct, 2)

    # 2026 prediction (round 1) per branch_name, representative open category.
    pred = {}
    for bname, pp in conn.execute(f"""
        SELECT branch_name, MIN(predicted_pct) FROM predictions_2026
        WHERE college_code IN ({placeholders}) AND round=1
          AND category IN ({tph})
        GROUP BY branch_name
    """, codes + list(TREND_CATEGORIES)):
        pred[bname] = round(pp, 2)

    branches = sorted(set(hist) | set(pred),
                      key=lambda b: hist.get(b, {}).get(2025, 0), reverse=True)
    out = []
    for b in branches:
        out.append({
            "branch_name": b,
            "close_2023": hist.get(b, {}).get(2023),
            "close_2024": hist.get(b, {}).get(2024),
            "close_2025": hist.get(b, {}).get(2025),
            "pred_2026": pred.get(b),
        })
    return out


DSE_TREND_CATEGORY = "GOPEN"


def _dse_cutoff_trends(conn, codes):
    """
    DSE twin of _cutoff_trends: per-branch (course_name) closing % across
    years for the representative GOPEN category, plus the latest-round
    carry-forward prediction from dse_predictions. Round 1 only, same
    reasoning as FE (a later round's close is always lower and would make
    the trend line lie). Returns [] (not an error) for colleges with no
    DSE data at all -- absence of DSE offerings is a normal, common case,
    not a fault condition.
    """
    placeholders = ",".join("?" * len(codes))

    hist = {}
    identity = {}   # course_name -> (max_year_seen, canonical_code) for linking
    for cname, year, pct, college_name, choice_code in conn.execute(f"""
        SELECT course_name, year, MIN(merit_pct), college_name, choice_code
        FROM dse_cutoffs
        WHERE college_code IN ({placeholders})
          AND category = ?
          AND round = 1
        GROUP BY course_name, year
    """, codes + [DSE_TREND_CATEGORY]):
        if year in hist.get(cname, {}):
            pct = min(pct, hist[cname][year])
        hist.setdefault(cname, {})[year] = round(pct, 2)
        # Keep the newest year's identity for the canonical_code, same rule
        # generate_dse_predictions.py uses ("meta" dict) -- so this link
        # resolves to the SAME canonical_code the DSE predictions were stored
        # under, never a mismatched one computed from stale-year fields.
        if cname not in identity or year >= identity[cname][0]:
            identity[cname] = (year, canonical_branch_key(college_name, cname, choice_code))

    pred = {}
    for cname, pp in conn.execute(f"""
        SELECT branch_name, MIN(predicted_pct) FROM dse_predictions
        WHERE college_code IN ({placeholders}) AND round=1 AND category=?
        GROUP BY branch_name
    """, codes + [DSE_TREND_CATEGORY]):
        pred[cname] = round(pp, 2)

    branches = sorted(set(hist) | set(pred),
                      key=lambda b: hist.get(b, {}).get(2025, 0), reverse=True)
    out = []
    for b in branches:
        out.append({
            "branch_name": b,
            "canonical_code": identity.get(b, (None, None))[1],
            "close_2023": hist.get(b, {}).get(2023),
            "close_2024": hist.get(b, {}).get(2024),
            "close_2025": hist.get(b, {}).get(2025),
            "pred_next": pred.get(b),
        })
    return out


def get_college_profile(college_code):
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA journal_mode=WAL")
    try:
        codes, name = _paired_codes(conn, college_code)
        if not codes:
            return {"error": f"No college found with code {college_code}"}

        p = _profile(conn, college_code)
        fees = {cat: compute_fee(conn, college_code, cat) for cat in FEE_CATEGORIES}
        # If the queried code lacks fee data, try a paired code.
        if not any(f["available"] for f in fees.values()):
            for code in codes:
                trial = {cat: compute_fee(conn, code, cat) for cat in FEE_CATEGORIES}
                if any(f["available"] for f in trial.values()):
                    fees = trial
                    break

        images = []
        # Prefer locally-downloaded photos — no CDN dependency, no Referer
        # blocking. Falls back to remote metadata for colleges the one-time
        # download hasn't reached yet (or that have no gps-cs-s photos at all).
        if p.get("local_image_paths"):
            try:
                local_paths = json.loads(p["local_image_paths"])
                images = [
                    {"url": f"{API_PUBLIC_BASE}/static/images/{path}", "type": "campus"}
                    for path in local_paths
                ]
            except Exception:
                images = []

        if not images and p.get("image_metadata"):
            try:
                raw = json.loads(p["image_metadata"])
                # grass-cs subdomain URLs are malformed (contain HTML entities) and
                # fail with ERR_BLOCKED_BY_ORB in browsers — exclude them entirely.
                images = [img for img in raw if "grass-cs" not in img.get("url", "")]
            except Exception:
                images = []

        return {
            "college_code": college_code,
            "paired_codes": codes,
            "college_name": name,
            "identity": {
                "institution_type": p.get("institution_type"),
                "management_name": p.get("management_name"),
                "year_established": p.get("year_established"),
                "is_autonomous": p.get("is_autonomous"),
            },
            "accreditation": {
                "naac_grade": p.get("naac_grade"),
                "naac_score": p.get("naac_score"),
                "nirf_rank": p.get("nirf_rank"),
                "nba_branches": p.get("nba_branches"),
            },
            "location": {
                "district": p.get("district"),
                "university_code": p.get("university_code"),
                "affiliated_university": p.get("affiliated_university"),
                "address": p.get("address"),
                "latitude": p.get("latitude"), "longitude": p.get("longitude"),
                "google_maps_url": p.get("google_maps_url"),
            },
            "contact": {"website_url": p.get("website_url"),
                        "email": p.get("email"), "phone": p.get("phone")},
            "facilities": {
                "hostel_boys": p.get("has_hostel_boys"),
                "hostel_girls": p.get("has_hostel_girls"),
                "sports": p.get("has_sports"), "wifi": p.get("has_wifi"),
                "campus_area_acres": p.get("campus_area_acres"),
            },
            "placements": {
                "placement_pct": p.get("placement_pct"),
                "avg_package_lpa": p.get("avg_package_lpa"),
                "highest_package_lpa": p.get("highest_package_lpa"),
                "top_recruiters": p.get("top_recruiters"),
                "reliable": bool(p.get("placement_reliable")),
            },
            "fees": fees,
            "score": _scores(conn, codes),
            "images": images,
            "image_count": len(images),
            "cutoff_trends": _cutoff_trends(conn, codes),
            "dse_cutoff_trends": _dse_cutoff_trends(conn, codes),
        }
    finally:
        conn.close()


def print_card(data):
    if "error" in data:
        print("ERROR:", data["error"]); return
    print(f"\n{'='*90}\n  {data['college_name']}  ({', '.join(data['paired_codes'])})\n{'='*90}")
    i, a, l = data["identity"], data["accreditation"], data["location"]
    print(f"  Type: {i['institution_type']}   Est: {i['year_established']}   "
          f"Autonomous: {i['is_autonomous']}")
    print(f"  University: {l['affiliated_university']} ({l['university_code']})   "
          f"District: {l['district']}")
    print(f"  NAAC: {a['naac_grade']}   NIRF: {a['nirf_rank']}   "
          f"Score: {data['score']['overall']}/100   Images: {data['image_count']}")
    f = data["facilities"]
    print(f"  Facilities -> hostel(B/G): {f['hostel_boys']}/{f['hostel_girls']}  "
          f"wifi: {f['wifi']}  sports: {f['sports']}")
    print("\n  Annual fee by category:")
    for cat, fee in data["fees"].items():
        if fee["available"]:
            print(f"    {cat:7} Rs {fee['total_annual']:>8,}  ({fee['fee_class']})")
        else:
            print(f"    {cat:7} {'unavailable':>12}  ({fee.get('reason')})")
    print("\n  Cutoff trends (open seats, closing %):")
    print(f"    {'Branch':<40} {'2023':>7} {'2024':>7} {'2025':>7} {'2026*':>7}")
    for t in data["cutoff_trends"][:12]:
        def s(v): return f"{v:.1f}" if v is not None else "-"
        print(f"    {t['branch_name'][:38]:<40} {s(t['close_2023']):>7} "
              f"{s(t['close_2024']):>7} {s(t['close_2025']):>7} {s(t['pred_2026']):>7}")
    print()


def main():
    p = argparse.ArgumentParser(description="EduPath Phase 4 — college profile card.")
    p.add_argument("--code", type=str, help="College code (4- or 5-digit)")
    p.add_argument("--name", type=str, help="Resolve by name substring instead")
    p.add_argument("--json", action="store_true", help="Print raw JSON")
    a = p.parse_args()

    code = a.code
    if a.name and not code:
        conn = sqlite3.connect(DB_PATH)
        row = conn.execute(
            "SELECT college_code FROM colleges WHERE college_name LIKE ? "
            "AND LENGTH(college_code)=5 LIMIT 1", (f"%{a.name}%",)).fetchone()
        conn.close()
        if not row:
            print("No college matches that name."); return
        code = row[0]
    if not code:
        print("Provide --code or --name."); return

    data = get_college_profile(code)
    if a.json:
        print(json.dumps(data, indent=2, ensure_ascii=False))
    else:
        print_card(data)


if __name__ == "__main__":
    main()
