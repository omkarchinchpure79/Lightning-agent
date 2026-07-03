import asyncio
from typing import Any

from fastapi import APIRouter

import engine_adapter as ea
from api.db import get_conn

router = APIRouter()


@router.get("/districts")
async def districts() -> list[str]:
    return await asyncio.to_thread(ea.list_districts)


@router.get("/categories")
async def categories() -> list[dict[str, str]]:
    return [{"label": label, "code": code} for label, code in ea.CATEGORY_OPTIONS]


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
            return {
                "score_min": score_row[0],
                "score_max": score_row[1],
                "year_min": year_row[0],
                "year_max": year_row[1],
            }
        finally:
            conn.close()

    return await asyncio.to_thread(_fetch)
