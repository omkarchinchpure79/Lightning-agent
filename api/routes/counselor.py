"""
counselor.py — Counselor-scoped shortlist and profile endpoints.

All routes require a valid JWT (Bearer token).

GET    /api/me/shortlist           — list saved colleges
POST   /api/me/shortlist           — add or ignore-if-exists a college
DELETE /api/me/shortlist/{code}    — remove a college
POST   /api/me/shortlist/bulk      — bulk-add (used for pre-login merge)
"""
import asyncio

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional

from api.auth_utils import get_current_counselor_id
from api.db import get_app_conn

router = APIRouter()


class ShortlistCollegeIn(BaseModel):
    college_code: str
    college_name: Optional[str] = None
    city: Optional[str] = None
    score: Optional[float] = None
    institution_type: Optional[str] = None


class ShortlistCollegeOut(ShortlistCollegeIn):
    saved_at: str


@router.get("/shortlist", response_model=list[ShortlistCollegeOut])
async def get_shortlist(counselor_id: int = Depends(get_current_counselor_id)):
    def _fetch():
        conn = get_app_conn()
        try:
            rows = conn.execute(
                """SELECT college_code, college_name, city, score, institution_type, saved_at
                   FROM counselor_shortlists
                   WHERE counselor_id = ?
                   ORDER BY saved_at DESC""",
                (counselor_id,),
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    return await asyncio.to_thread(_fetch)


@router.post("/shortlist", response_model=ShortlistCollegeOut, status_code=201)
async def add_to_shortlist(
    body: ShortlistCollegeIn,
    counselor_id: int = Depends(get_current_counselor_id),
):
    def _upsert():
        conn = get_app_conn()
        try:
            conn.execute(
                """INSERT INTO counselor_shortlists
                       (counselor_id, college_code, college_name, city, score, institution_type)
                   VALUES (?, ?, ?, ?, ?, ?)
                   ON CONFLICT(counselor_id, college_code) DO NOTHING""",
                (
                    counselor_id,
                    body.college_code,
                    body.college_name,
                    body.city,
                    body.score,
                    body.institution_type,
                ),
            )
            conn.commit()
            return conn.execute(
                "SELECT college_code, college_name, city, score, institution_type, saved_at "
                "FROM counselor_shortlists WHERE counselor_id = ? AND college_code = ?",
                (counselor_id, body.college_code),
            ).fetchone()
        finally:
            conn.close()

    row = await asyncio.to_thread(_upsert)
    return dict(row)


@router.delete("/shortlist/{college_code}", status_code=204)
async def remove_from_shortlist(
    college_code: str,
    counselor_id: int = Depends(get_current_counselor_id),
):
    def _delete():
        conn = get_app_conn()
        try:
            conn.execute(
                "DELETE FROM counselor_shortlists WHERE counselor_id = ? AND college_code = ?",
                (counselor_id, college_code),
            )
            conn.commit()
        finally:
            conn.close()

    await asyncio.to_thread(_delete)


class BulkShortlistRequest(BaseModel):
    items: list[ShortlistCollegeIn]


@router.post("/shortlist/bulk", status_code=204)
async def bulk_add_shortlist(
    body: BulkShortlistRequest,
    counselor_id: int = Depends(get_current_counselor_id),
):
    """Import multiple colleges at once (used when merging a pre-login localStorage list)."""
    def _bulk():
        conn = get_app_conn()
        try:
            conn.executemany(
                """INSERT INTO counselor_shortlists
                       (counselor_id, college_code, college_name, city, score, institution_type)
                   VALUES (?, ?, ?, ?, ?, ?)
                   ON CONFLICT(counselor_id, college_code) DO NOTHING""",
                [
                    (counselor_id, item.college_code, item.college_name,
                     item.city, item.score, item.institution_type)
                    for item in body.items
                ],
            )
            conn.commit()
        finally:
            conn.close()

    await asyncio.to_thread(_bulk)
