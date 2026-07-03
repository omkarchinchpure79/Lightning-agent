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
from api.db import get_conn
from api.schemas import CollegeSearchResult

router = APIRouter()

# Base URL the frontend can reach the API's own static image mount at.
# Local dev default matches NEXT_PUBLIC_API_URL's default in web/lib/api.ts.
_API_PUBLIC_BASE = os.environ.get("API_PUBLIC_BASE", "http://localhost:8000")


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
    branch: Optional[str] = Query(default=None),
    limit: int = Query(default=20, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
):
    """
    Substring search on college name (case-insensitive).
    Empty q = browse mode, ordered by score DESC.
    Supports limit/offset for pagination. Max limit 200.
    Per physical college, the 5-digit code is preferred over the legacy 4-digit code.
    """
    def _query():
        conn = get_conn()
        try:
            params: list = []

            name_filter = ""
            if q:
                name_filter = "WHERE LOWER(c.college_name) LIKE LOWER(?)"
                params.append(f"%{q}%")

            district_filter = ""
            if district:
                district_filter = "AND LOWER(cd.district) LIKE LOWER(?)"
                params.append(f"%{district}%")

            type_filter = ""
            if institution_type:
                type_filter = "AND cd.institution_type = ?"
                params.append(institution_type)

            naac_filter = ""
            if naac_above_a:
                naac_filter = "AND cd.naac_grade IN ('A', 'A+', 'A++')"
            elif naac_grade:
                naac_filter = "AND cd.naac_grade = ?"
                params.append(naac_grade)

            year_filter = ""
            if year_min is not None:
                year_filter += "AND cd.year_established >= ? "
                params.append(year_min)
            if year_max is not None:
                year_filter += "AND cd.year_established <= ? "
                params.append(year_max)

            score_filter = ""
            if score_min is not None:
                score_filter += "AND r.score >= ? "
                params.append(score_min)
            if score_max is not None:
                score_filter += "AND r.score <= ? "
                params.append(score_max)

            branch_filter = ""
            if branch:
                # Branch rows aren't always mirrored across the 4-digit/5-digit
                # code pair for the same physical college, so match by college
                # NAME (any code variant), not just the code `ranked` picked.
                branch_filter = """AND EXISTS (
                    SELECT 1 FROM branches b
                    JOIN colleges c2 ON c2.college_code = b.college_code
                    WHERE c2.college_name = r.college_name
                      AND LOWER(b.branch_name) LIKE LOWER(?)
                )"""
                params.append(f"%{branch}%")

            # One row per physical college: prefer the 5-digit code (newer).
            sql = f"""
                WITH ranked AS (
                    SELECT c.college_code, c.college_name, c.city, c.score,
                           ROW_NUMBER() OVER (
                               PARTITION BY c.college_name
                               ORDER BY LENGTH(c.college_code) DESC
                           ) AS rn
                    FROM colleges c
                    {name_filter}
                )
                SELECT r.college_code, r.college_name, r.city, r.score,
                       cd.district, cd.institution_type, cd.naac_grade,
                       cd.image_urls AS _image_urls_json,
                       cd.local_image_paths AS _local_paths_json,
                       CASE WHEN cd.image_urls LIKE '%gps-cs-s%'
                              OR cd.local_image_paths IS NOT NULL
                            THEN 1 ELSE 0 END AS has_photo
                FROM ranked r
                LEFT JOIN college_details cd ON cd.college_code = r.college_code
                WHERE r.rn = 1
                  {district_filter}
                  {type_filter}
                  {naac_filter}
                  {year_filter}
                  {score_filter}
                  {branch_filter}
                ORDER BY has_photo DESC, r.score DESC
                LIMIT ? OFFSET ?
            """
            import json as _json, re as _re
            params.extend([limit, offset])
            rows = conn.execute(sql, params).fetchall()
            results = []
            for r in rows:
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
    representative open categories). Returns predicted close and a link to
    the canonical_code for the branch deep-dive endpoint.
    """
    OPEN_CATS = ("GOPENH", "GOPENS", "GOPENO")

    def _query():
        conn = get_conn()
        try:
            row = conn.execute(
                "SELECT college_name FROM colleges WHERE college_code = ?",
                (college_code,),
            ).fetchone()
            if not row:
                return None
            college_name = row[0]
            codes = [
                r[0]
                for r in conn.execute(
                    "SELECT college_code FROM colleges WHERE college_name = ?",
                    (college_name,),
                )
            ]
            ph = ",".join("?" * len(codes))
            cat_ph = ",".join("?" * len(OPEN_CATS))
            rows = conn.execute(
                f"""
                SELECT p.canonical_code, p.branch_name,
                       MIN(p.predicted_pct) AS pred_close,
                       p.confidence, p.years_used
                FROM predictions_2026 p
                WHERE p.college_code IN ({ph})
                  AND p.round = 1
                  AND p.category IN ({cat_ph})
                GROUP BY p.canonical_code, p.branch_name
                ORDER BY pred_close DESC
                """,
                codes + list(OPEN_CATS),
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
        conn = get_conn()
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
        conn = get_conn()
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
        conn = get_conn()
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
        conn = get_conn()
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
            row = conn.execute(
                "SELECT college_name FROM colleges WHERE college_code = ?",
                (college_code,),
            ).fetchone()
            if not row:
                return None
            name = row[0]
            codes = [
                r[0]
                for r in conn.execute(
                    "SELECT college_code FROM colleges WHERE college_name = ?", (name,)
                )
            ]
            return set(codes)
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
