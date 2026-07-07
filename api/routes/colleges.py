"""
colleges.py — college search, full profile, branch listing, round strategy.

/search is defined before /{college_code} so FastAPI matches "search" as a
literal path segment first and never treats it as a code value.

Image CDN URLs are returned as-is from college_card_api; the image_warning
field reminds consumers not to proxy them (Google Maps CDN, signed URLs,
ToS risk).
"""
import asyncio
import os
from typing import Optional

import anthropic
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

import engine_adapter as ea
from api.db import get_conn, get_app_conn
from api.schemas import CollegeSearchResult
from constants import canonical_college_key

router = APIRouter()

# Base URL the frontend can reach the API's own static image mount at.
# Local dev default matches NEXT_PUBLIC_API_URL's default in web/lib/api.ts.
_API_PUBLIC_BASE = os.environ.get("API_PUBLIC_BASE", "http://localhost:8000")


def _canonical_groups(conn):
    """
    {canonical_key: [college_code, ...]} for every college in the DB. Single
    place this file resolves "same physical college" — by canonical_college_key
    (code identity), NOT exact college_name match. Real CET Cell PDFs don't
    repeat identical name text year to year even for the unchanged college
    (district renames, dropped trust-name prefixes), so name-equality silently
    left 32 physical colleges showing as duplicate rows in /search and missing
    branches/cutoffs in /branches + /strategy (audit 2026-07-05).
    """
    groups: dict[str, list[str]] = {}
    for code, name in conn.execute("SELECT college_code, college_name FROM colleges"):
        groups.setdefault(canonical_college_key(code, name), []).append(code)
    return groups


def _sibling_codes(conn, college_code):
    """All codes sharing college_code's canonical identity (itself included)."""
    row = conn.execute(
        "SELECT college_name FROM colleges WHERE college_code = ?", (college_code,)
    ).fetchone()
    if not row:
        return None, None
    name = row[0]
    key = canonical_college_key(college_code, name)
    codes = [
        c for c, n in conn.execute("SELECT college_code, college_name FROM colleges")
        if canonical_college_key(c, n) == key
    ]
    return codes, name


# ---------------------------------------------------------------------------
# Search — must come before /{college_code} to avoid shadowing
# ---------------------------------------------------------------------------

@router.get("/search", response_model=list[CollegeSearchResult])
async def search_colleges(
    q: str = Query(default=""),
    district: Optional[str] = Query(default=None),
    institution_type: Optional[str] = Query(default=None),
    naac_above_a: bool = Query(default=False),
    naac_grade: Optional[str] = Query(default=None),
    year_min: Optional[int] = Query(default=None),
    year_max: Optional[int] = Query(default=None),
    score_min: Optional[float] = Query(default=None),
    score_max: Optional[float] = Query(default=None),
    percentile_min: Optional[float] = Query(default=None, ge=0.0, le=100.0),
    percentile_max: Optional[float] = Query(default=None, ge=0.0, le=100.0),
    branch: Optional[str] = Query(default=None),
    sort_by: str = Query(default="score", pattern="^(score|percentile)$"),
    limit: int = Query(default=20, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
):
    """
    Substring search on college name (case-insensitive).
    Empty q = browse mode, ordered by score DESC (or top_percentile DESC when
    sort_by=percentile — the college's toughest branch's real closing
    percentile, GOPEN-equivalent Round 1, latest available year; same
    definition score_colleges.py uses for the selectivity subset).
    Supports limit/offset for pagination. Max limit 200.
    Per physical college, the 5-digit code is preferred over the legacy 4-digit code.
    """
    def _query():
        conn = get_conn()
        try:
            params: list = []
            clauses: list[str] = []

            if q:
                clauses.append("LOWER(c.college_name) LIKE LOWER(?)")
                params.append(f"%{q}%")
            if district:
                clauses.append("LOWER(cd.district) LIKE LOWER(?)")
                params.append(f"%{district}%")
            if institution_type:
                clauses.append("cd.institution_type = ?")
                params.append(institution_type)
            if naac_above_a:
                clauses.append("cd.naac_grade IN ('A', 'A+', 'A++')")
            elif naac_grade:
                clauses.append("cd.naac_grade = ?")
                params.append(naac_grade)
            if year_min is not None:
                clauses.append("cd.year_established >= ?")
                params.append(year_min)
            if year_max is not None:
                clauses.append("cd.year_established <= ?")
                params.append(year_max)
            if score_min is not None:
                clauses.append("c.score >= ?")
                params.append(score_min)
            if score_max is not None:
                clauses.append("c.score <= ?")
                params.append(score_max)
            if percentile_min is not None:
                clauses.append("c.top_percentile >= ?")
                params.append(percentile_min)
            if percentile_max is not None:
                clauses.append("c.top_percentile <= ?")
                params.append(percentile_max)

            where_sql = ("WHERE " + " AND ".join(clauses)) if clauses else ""
            order_column = "score" if sort_by == "score" else "top_percentile"

            # Fetch every matching CODE (no dedup, no pagination yet) — dedup
            # to one row per physical college happens in Python below, keyed
            # by canonical_college_key, since that identity can't be expressed
            # as a SQL PARTITION BY (it needs the RECODED_COLLEGES name-fragment
            # fallback, which is Python logic).
            sql = f"""
                SELECT c.college_code, c.college_name, c.city, c.score, c.top_percentile,
                       cd.district, cd.institution_type, cd.naac_grade,
                       cd.image_urls AS _image_urls_json,
                       cd.local_image_paths AS _local_paths_json,
                       CASE WHEN cd.image_urls LIKE '%gps-cs-s%'
                              OR cd.local_image_paths IS NOT NULL
                            THEN 1 ELSE 0 END AS has_photo
                FROM colleges c
                LEFT JOIN college_details cd ON cd.college_code = c.college_code
                {where_sql}
            """
            candidates = conn.execute(sql, params).fetchall()

            # Branch filter: match against ANY code sharing a candidate's
            # canonical identity, not just the exact code that happened to
            # carry the branches rows (siblings don't always mirror branches).
            if branch:
                groups = _canonical_groups(conn)
                key_by_code = {c: k for k, codes in groups.items() for c in codes}
                matched_codes = {
                    r[0] for r in conn.execute(
                        "SELECT DISTINCT college_code FROM branches WHERE LOWER(branch_name) LIKE LOWER(?)",
                        (f"%{branch}%",),
                    )
                }
                matched_keys = {key_by_code[c] for c in matched_codes if c in key_by_code}
                candidates = [
                    r for r in candidates
                    if key_by_code.get(r["college_code"]) in matched_keys
                ]

            # Dedup to one row per physical college: prefer has_photo, then the
            # 5-digit (newer) code — same preference the old SQL PARTITION used.
            best_by_key: dict = {}
            for r in candidates:
                key = canonical_college_key(r["college_code"], r["college_name"])
                cur_best = best_by_key.get(key)
                if cur_best is None or (r["has_photo"], len(r["college_code"])) > (
                    cur_best["has_photo"], len(cur_best["college_code"])
                ):
                    best_by_key[key] = r

            def _sort_key(r):
                metric = r[order_column]
                return (r["has_photo"], metric if metric is not None else -1)

            ordered = sorted(best_by_key.values(), key=_sort_key, reverse=True)
            page = ordered[offset:offset + limit]

            import json as _json, re as _re
            results = []
            for r in page:
                d = dict(r)
                d.pop("has_photo", None)
                raw_urls = d.pop("_image_urls_json", None)
                raw_local = d.pop("_local_paths_json", None)
                thumbnail_url = None

                # Prefer the locally-downloaded copy — no CDN dependency, no
                # Referer blocking. Falls back to the live Google CDN URL for
                # colleges the one-time download hasn't reached yet.
                if raw_local:
                    try:
                        local_paths = _json.loads(raw_local)
                        if local_paths:
                            thumbnail_url = f"{_API_PUBLIC_BASE}/static/images/{local_paths[0]}"
                    except Exception:
                        pass

                if thumbnail_url is None and raw_urls:
                    try:
                        urls = _json.loads(raw_urls)
                        # Only use gps-cs-s (Google Maps place photos) — these are
                        # genuine campus exterior shots with predictable dimensions.
                        # a-/ALV- user-contributed photos can be logos, portraits,
                        # or scanned documents; Wikipedia/college-site URLs are
                        # often emblems or event banners. All of these look wrong
                        # in a 180px landscape card. Show a placeholder instead.
                        campus = [
                            u for u in urls
                            if isinstance(u, str)
                            and "gps-cs-s" in u
                            and u.startswith("http")
                        ]
                        if campus:
                            chosen = _re.sub(
                                r"=w\d+-h\d+.*", "=w600-h400-k-no", campus[0]
                            )
                            thumbnail_url = chosen
                    except Exception:
                        pass
                d["thumbnail_url"] = thumbnail_url
                results.append(d)
            return results
        finally:
            conn.close()

    return await asyncio.to_thread(_query)


# ---------------------------------------------------------------------------
# Full profile
# ---------------------------------------------------------------------------

@router.get("/{college_code}")
async def college_profile(college_code: str):
    result = await asyncio.to_thread(ea.college_profile, college_code)
    if "error" in result:
        raise HTTPException(404, result["error"])
    result["image_warning"] = "CDN URLs — display only, do not proxy"
    return result


# ---------------------------------------------------------------------------
# Branch listing for a college
# ---------------------------------------------------------------------------

@router.get("/{college_code}/branches")
async def college_branches(college_code: str):
    """
    All distinct branches at this college (from predictions_2026 round 1,
    representative open categories). Returns predicted 2026 close, the actual
    2025 close (same open-category convention as college_card_api's cutoff
    trend line), confidence, the official CET course/branch code (representative
    10-digit code for the branch), and seat intake (general/TFWS, from branch_intake
    — parsed from the official CET Cell seat-matrix PDFs, see
    parse_seat_intake.py; None where a college's intake PDF wasn't available
    or didn't parse, never a guessed number).
    """
    OPEN_CATS = ("GOPENH", "GOPENS", "GOPENO")

    def _query():
        conn = get_conn()
        try:
            codes, college_name = _sibling_codes(conn, college_code)
            if codes is None:
                return None
            ph = ",".join("?" * len(codes))
            cat_ph = ",".join("?" * len(OPEN_CATS))
            rows = conn.execute(
                f"""
                WITH closes_2025 AS (
                    SELECT b.branch_name, MIN(cu.percentile) AS close_2025
                    FROM cutoffs cu JOIN branches b ON cu.branch_code = b.branch_code
                    WHERE b.college_code IN ({ph})
                      AND cu.year = 2025 AND cu.round = 1
                      AND cu.category IN ({cat_ph})
                      AND cu.is_all_india = 0
                    GROUP BY b.branch_name
                )
                SELECT p.canonical_code, p.branch_name,
                       MIN(p.predicted_pct) AS pred_close,
                       p.confidence, p.years_used,
                       MAX(p.branch_code) AS branch_code,
                       MAX(c25.close_2025) AS close_2025,
                       MAX(bi.general_intake) AS general_intake,
                       MAX(bi.tfws_intake) AS tfws_intake
                FROM predictions_2026 p
                LEFT JOIN closes_2025 c25 ON c25.branch_name = p.branch_name
                LEFT JOIN branch_intake bi ON bi.canonical_code = p.canonical_code
                WHERE p.college_code IN ({ph})
                  AND p.round = 1
                  AND p.category IN ({cat_ph})
                GROUP BY p.canonical_code, p.branch_name
                ORDER BY pred_close DESC
                """,
                codes + list(OPEN_CATS) + codes + list(OPEN_CATS),
            ).fetchall()
            return {
                "college_code": college_code,
                "college_name": college_name,
                "branches": [dict(r) for r in rows],
            }
        finally:
            conn.close()

    result = await asyncio.to_thread(_query)
    if result is None:
        raise HTTPException(404, f"College {college_code} not found")
    return result


# ---------------------------------------------------------------------------
# AI-generated description (cached in college_descriptions table)
# ---------------------------------------------------------------------------

class DescriptionResponse(BaseModel):
    college_code: str
    description: str
    generated_at: str
    edited_by_counselor: bool
    from_cache: bool


class DescriptionEditRequest(BaseModel):
    description: str


def _build_prompt(profile: dict) -> str:
    name = profile.get("college_name", "this college")
    identity = profile.get("identity", {})
    acc = profile.get("accreditation", {})
    loc = profile.get("location", {})
    place = profile.get("placements", {})

    naac = acc.get("naac_grade") or "N/A"
    nirf = f"#{acc.get('nirf_rank')}" if acc.get("nirf_rank") else "not ranked"
    place_pct = f"{place.get('placement_pct')}%" if place.get("placement_pct") is not None else "data unavailable"
    avg_pkg = f"{place.get('avg_package_lpa')} LPA" if place.get("avg_package_lpa") is not None else ""
    recruiters = place.get("top_recruiters") or ""
    inst_type = identity.get("institution_type") or ""
    district = loc.get("district") or ""
    year_est = identity.get("year_established") or ""
    university = loc.get("affiliated_university") or ""

    return f"""Write a friendly, warm description of {name} for a college counsellor's tool used in Maharashtra, India.

College facts:
- Type: {inst_type}
- Location: {district}, Maharashtra
- Affiliated to: {university}
- Established: {year_est}
- NAAC grade: {naac}
- NIRF rank: {nirf}
- Placement rate: {place_pct}  {f'· Avg package: {avg_pkg}' if avg_pkg else ''}
- Top recruiters: {recruiters if recruiters else 'not available'}

Write 3–4 sentences covering:
1. 💡 What the college is known for and its strengths
2. 👥 Which type of student it's best suited for
3. 🌟 What makes it unique (location, culture, infrastructure, programs)
4. 🎯 Key stats: NAAC, NIRF, placement % and one standout recruiter if known

Rules:
- Use emojis as bullet markers (💡 👥 🌟 🎯) — one per line
- Friendly, encouraging tone — not corporate brochure language
- Under 200 words
- If data is unavailable for a point, skip that point rather than saying "data unavailable"
- Do NOT invent stats; only use the facts provided above"""


def _get_cached_description(conn, college_code: str):
    return conn.execute(
        "SELECT college_code, description, generated_at, edited_by_counselor "
        "FROM college_descriptions WHERE college_code = ?",
        (college_code,),
    ).fetchone()


@router.get("/{college_code}/description", response_model=DescriptionResponse)
async def get_description(college_code: str):
    """Return cached AI description; 404 if not yet generated."""
    def _read():
        conn = get_app_conn()
        try:
            return _get_cached_description(conn, college_code)
        finally:
            conn.close()

    row = await asyncio.to_thread(_read)
    if not row:
        raise HTTPException(404, "No description generated yet. POST to generate.")
    return DescriptionResponse(
        college_code=row["college_code"],
        description=row["description"],
        generated_at=row["generated_at"],
        edited_by_counselor=bool(row["edited_by_counselor"]),
        from_cache=True,
    )


@router.post("/{college_code}/generate-description", response_model=DescriptionResponse)
async def generate_description(college_code: str, force: bool = Query(default=False)):
    """
    Generate (or regenerate) an AI description for this college.

    Checks the DB cache first; returns the cached version unless force=true.
    Calls the Claude API once per college (Haiku 4.5 — cheap, fast, good enough).
    Stores the result in college_descriptions.
    """
    # 1 — Check cache (skip if force=true)
    def _read_cache():
        conn = get_app_conn()
        try:
            return _get_cached_description(conn, college_code)
        finally:
            conn.close()

    if not force:
        cached = await asyncio.to_thread(_read_cache)
        if cached:
            return DescriptionResponse(
                college_code=cached["college_code"],
                description=cached["description"],
                generated_at=cached["generated_at"],
                edited_by_counselor=bool(cached["edited_by_counselor"]),
                from_cache=True,
            )

    # 2 — Fetch college profile for context
    profile = await asyncio.to_thread(ea.college_profile, college_code)
    if "error" in profile:
        raise HTTPException(404, profile["error"])

    # 3 — Call Claude API
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise HTTPException(503, "ANTHROPIC_API_KEY not set — cannot generate description.")

    client = anthropic.Anthropic(api_key=api_key)
    prompt = _build_prompt(profile)

    def _call_claude():
        msg = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=400,
            messages=[{"role": "user", "content": prompt}],
        )
        return msg.content[0].text.strip()

    description = await asyncio.to_thread(_call_claude)

    # 4 — Store in DB (upsert)
    def _store(desc: str):
        conn = get_app_conn()
        try:
            conn.execute(
                """
                INSERT INTO college_descriptions (college_code, description, generated_at, edited_by_counselor)
                VALUES (?, ?, datetime('now'), 0)
                ON CONFLICT(college_code) DO UPDATE SET
                    description    = excluded.description,
                    generated_at   = excluded.generated_at,
                    edited_by_counselor = 0
                """,
                (college_code, desc),
            )
            conn.commit()
            return _get_cached_description(conn, college_code)
        finally:
            conn.close()

    row = await asyncio.to_thread(_store, description)
    return DescriptionResponse(
        college_code=row["college_code"],
        description=row["description"],
        generated_at=row["generated_at"],
        edited_by_counselor=bool(row["edited_by_counselor"]),
        from_cache=False,
    )


@router.patch("/{college_code}/description", response_model=DescriptionResponse)
async def edit_description(college_code: str, body: DescriptionEditRequest):
    """Counsellor override — saves edited text and sets edited_by_counselor=1."""
    def _update():
        conn = get_app_conn()
        try:
            conn.execute(
                """
                INSERT INTO college_descriptions (college_code, description, generated_at, edited_by_counselor)
                VALUES (?, ?, datetime('now'), 1)
                ON CONFLICT(college_code) DO UPDATE SET
                    description         = excluded.description,
                    generated_at        = excluded.generated_at,
                    edited_by_counselor = 1
                """,
                (college_code, body.description),
            )
            conn.commit()
            return _get_cached_description(conn, college_code)
        finally:
            conn.close()

    row = await asyncio.to_thread(_update)
    return DescriptionResponse(
        college_code=row["college_code"],
        description=row["description"],
        generated_at=row["generated_at"],
        edited_by_counselor=bool(row["edited_by_counselor"]),
        from_cache=False,
    )


# ---------------------------------------------------------------------------
# Round strategy for a specific college
# ---------------------------------------------------------------------------

@router.get("/{college_code}/strategy")
async def college_strategy(
    college_code: str,
    percentile: float = Query(..., ge=0.0, le=100.0),
    category_label: str = Query(...),
    home_district: Optional[str] = Query(default=None),
):
    """
    Lock-vs-wait advice filtered to a specific college. Returns the same
    structure as /api/predictions' round-strategy, restricted to branches
    at this college (across all paired codes for the physical college).
    """
    def _paired():
        conn = get_conn()
        try:
            codes, _name = _sibling_codes(conn, college_code)
            return set(codes) if codes is not None else None
        finally:
            conn.close()

    paired = await asyncio.to_thread(_paired)
    if paired is None:
        raise HTTPException(404, f"College {college_code} not found")

    data = await asyncio.to_thread(ea.round_strategy, percentile, category_label, home_district)
    if "error" in data:
        raise HTTPException(400, data["error"])

    filtered = [r for r in data.get("results", []) if r.get("college_code") in paired]
    return {**data, "results": filtered, "college_code": college_code}
