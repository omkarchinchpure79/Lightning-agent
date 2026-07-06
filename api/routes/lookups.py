import asyncio
from typing import Any

from fastapi import APIRouter

import engine_adapter as ea
from api.db import get_conn
from constants import canonical_college_key, DSE_CATEGORY_MAP, YEAR_WEIGHTS

router = APIRouter()


@router.get("/districts")
async def districts() -> list[str]:
    return await asyncio.to_thread(ea.list_districts)


@router.get("/categories")
async def categories() -> list[dict[str, Any]]:
    """Category dropdown options. dse_supported tells the student form which
    categories exist in the DSE data plane (e.g. TFWS is first-year only)."""
    return [
        {"label": label, "code": code,
         "dse_supported": DSE_CATEGORY_MAP.get(code) is not None}
        for label, code in ea.CATEGORY_OPTIONS
    ]


@router.get("/branches")
async def branch_keywords() -> list[str]:
    return ea.list_branch_keywords()


@router.get("/cap-rounds")
async def cap_rounds() -> list[int]:
    return [1, 2, 3]


@router.get("/naac-grades")
async def naac_grades() -> list[str]:
    """Distinct NAAC grades present in the data, best-first."""
    order = ["A++", "A+", "A", "B++", "B+", "B", "C"]

    def _fetch():
        conn = get_conn()
        try:
            rows = conn.execute(
                "SELECT DISTINCT naac_grade FROM college_details WHERE naac_grade IS NOT NULL"
            ).fetchall()
            return {r[0] for r in rows}
        finally:
            conn.close()

    present = await asyncio.to_thread(_fetch)
    return [g for g in order if g in present]


@router.get("/filter-ranges")
async def filter_ranges() -> dict[str, Any]:
    """Min/max bounds for the score and established-year sidebar sliders."""
    def _fetch():
        conn = get_conn()
        try:
            score_row = conn.execute(
                "SELECT MIN(score), MAX(score) FROM colleges WHERE score IS NOT NULL"
            ).fetchone()
            year_row = conn.execute(
                "SELECT MIN(year_established), MAX(year_established) "
                "FROM college_details WHERE year_established IS NOT NULL"
            ).fetchone()
            pct_row = conn.execute(
                "SELECT MIN(top_percentile), MAX(top_percentile) FROM colleges "
                "WHERE top_percentile IS NOT NULL"
            ).fetchone()
            return {
                "score_min": score_row[0],
                "score_max": score_row[1],
                "year_min": year_row[0],
                "year_max": year_row[1],
                "percentile_min": pct_row[0],
                "percentile_max": pct_row[1],
            }
        finally:
            conn.close()

    return await asyncio.to_thread(_fetch)


@router.get("/stats")
async def stats() -> dict[str, Any]:
    """
    Real, always-current homepage hero numbers — never hardcode these on the
    frontend (audit 2026-07-05: "11 yrs cutoff data" and "36 districts" were
    literal strings on the homepage that didn't match the actual data).
    college_count is the true PHYSICAL college count (grouped by
    canonical_college_key, same identity /search dedupes on) — not a raw
    colleges-table row count, which double-counts every 4-digit/5-digit pair.
    cutoff_year_* comes from constants.YEAR_WEIGHTS, the single source of
    truth for which years the prediction engine actually trains on.
    """
    def _fetch():
        conn = get_conn()
        try:
            rows = conn.execute("SELECT college_code, college_name FROM colleges").fetchall()
            college_count = len({canonical_college_key(c, n) for c, n in rows})
            return {
                "college_count": college_count,
                "district_count": len(ea.list_districts()),
                "cutoff_year_min": min(YEAR_WEIGHTS),
                "cutoff_year_max": max(YEAR_WEIGHTS),
                "cutoff_year_count": len(YEAR_WEIGHTS),
            }
        finally:
            conn.close()

    return await asyncio.to_thread(_fetch)
