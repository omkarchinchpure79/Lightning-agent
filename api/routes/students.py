"""
students.py — CRUD for student_profiles + shortlist persistence.

JSON list fields (preferred_branches, preferred_locations) are stored as JSON
text in SQLite and deserialised back to Python lists in every response.
PATCH uses model_dump(exclude_unset=True) so only sent fields are updated.
"""
import asyncio
import json
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException

from api.auth_utils import get_current_counselor_id
from api.db import get_conn
from api.schemas import (
    ShortlistItem, ShortlistRequest, ShortlistResponse,
    StudentCreate, StudentListItem, StudentResponse, StudentUpdate,
)

router = APIRouter()


def _owns(conn, student_id: int, counselor_id: int) -> bool:
    """True if this student profile belongs to this counselor."""
    row = conn.execute(
        "SELECT 1 FROM student_profiles WHERE id = ? AND counsellor_id = ?",
        (student_id, str(counselor_id)),
    ).fetchone()
    return row is not None

_BOOL_FIELDS = ("pwd_status", "defense_status", "tfws_eligible", "orphan_status", "ews_eligible")
_JSON_FIELDS = ("preferred_branches", "preferred_locations")


def _serialise_for_db(data: dict) -> dict:
    """Convert Python types to SQLite-friendly values."""
    out = dict(data)
    for f in _JSON_FIELDS:
        if f in out:
            out[f] = json.dumps(out[f]) if out[f] is not None else None
    for f in _BOOL_FIELDS:
        if f in out and out[f] is not None:
            out[f] = int(out[f])
    return out


def _row_to_student(row) -> dict:
    d = dict(row)
    for f in _JSON_FIELDS:
        raw = d.get(f)
        if raw is None:
            d[f] = None
        else:
            try:
                d[f] = json.loads(raw)
            except (json.JSONDecodeError, TypeError):
                d[f] = None
    for f in _BOOL_FIELDS:
        d[f] = bool(d.get(f, 0))
    return d


def _shortlist_item(row) -> ShortlistItem:
    d = dict(row)
    return ShortlistItem(
        canonical_code=d["canonical_code"],
        college_name=d.get("college_name"),
        branch_name=d.get("branch_name"),
        band=d.get("band"),
        predicted_close=d.get("predicted_close"),
        margin=d.get("margin"),
        confidence=d.get("confidence"),
        category_used=d.get("category_used"),
        seat_type=d.get("seat_type"),
        fee_text=d.get("fee_text"),
        branch_code=d.get("branch_code"),
        college_score=d.get("college_score"),
        seat_pool=d.get("seat_pool"),
    )


def _now_utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


# ---------------------------------------------------------------------------
# CRUD
# ---------------------------------------------------------------------------

@router.post("", status_code=201, response_model=StudentResponse)
async def create_student(
    body: StudentCreate,
    counselor_id: int = Depends(get_current_counselor_id),
):
    def _insert():
        data = _serialise_for_db(body.model_dump())
        data["counsellor_id"] = str(counselor_id)  # owner from JWT, ignore any client value
        cols = ", ".join(data.keys())
        placeholders = ", ".join("?" * len(data))
        conn = get_conn()
        try:
            cur = conn.execute(
                f"INSERT INTO student_profiles ({cols}) VALUES ({placeholders})",
                list(data.values()),
            )
            conn.commit()
            row = conn.execute(
                "SELECT * FROM student_profiles WHERE id = ?", (cur.lastrowid,)
            ).fetchone()
            return _row_to_student(row)
        finally:
            conn.close()

    result = await asyncio.to_thread(_insert)
    return StudentResponse(**result)


@router.get("", response_model=list[StudentListItem])
async def list_students(counselor_id: int = Depends(get_current_counselor_id)):
    def _query():
        conn = get_conn()
        try:
            rows = conn.execute(
                "SELECT id, name, percentile, category_base, home_district, updated_at "
                "FROM student_profiles WHERE counsellor_id = ? ORDER BY updated_at DESC",
                (str(counselor_id),),
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    return await asyncio.to_thread(_query)


@router.get("/{student_id}", response_model=StudentResponse)
async def get_student(
    student_id: int,
    counselor_id: int = Depends(get_current_counselor_id),
):
    def _query():
        conn = get_conn()
        try:
            row = conn.execute(
                "SELECT * FROM student_profiles WHERE id = ? AND counsellor_id = ?",
                (student_id, str(counselor_id)),
            ).fetchone()
            return _row_to_student(row) if row else None
        finally:
            conn.close()

    result = await asyncio.to_thread(_query)
    if result is None:
        raise HTTPException(404, f"Student {student_id} not found")
    return StudentResponse(**result)


@router.patch("/{student_id}", response_model=StudentResponse)
async def update_student(
    student_id: int,
    body: StudentUpdate,
    counselor_id: int = Depends(get_current_counselor_id),
):
    updates = body.model_dump(exclude_unset=True)
    updates.pop("counsellor_id", None)  # ownership is immutable via PATCH
    if not updates:
        raise HTTPException(400, "No fields provided to update")

    updates["updated_at"] = _now_utc()
    db_updates = _serialise_for_db(updates)

    def _update():
        set_clause = ", ".join(f"{k} = ?" for k in db_updates)
        values = list(db_updates.values()) + [student_id, str(counselor_id)]
        conn = get_conn()
        try:
            cur = conn.execute(
                f"UPDATE student_profiles SET {set_clause} "
                f"WHERE id = ? AND counsellor_id = ?", values
            )
            conn.commit()
            if cur.rowcount == 0:
                return None
            row = conn.execute(
                "SELECT * FROM student_profiles WHERE id = ?", (student_id,)
            ).fetchone()
            return _row_to_student(row)
        finally:
            conn.close()

    result = await asyncio.to_thread(_update)
    if result is None:
        raise HTTPException(404, f"Student {student_id} not found")
    return StudentResponse(**result)


@router.delete("/{student_id}", status_code=204)
async def delete_student(
    student_id: int,
    counselor_id: int = Depends(get_current_counselor_id),
):
    def _delete():
        conn = get_conn()
        try:
            cur = conn.execute(
                "DELETE FROM student_profiles WHERE id = ? AND counsellor_id = ?",
                (student_id, str(counselor_id)),
            )
            conn.commit()
            return cur.rowcount
        finally:
            conn.close()

    rows_deleted = await asyncio.to_thread(_delete)
    if rows_deleted == 0:
        raise HTTPException(404, f"Student {student_id} not found")


# ---------------------------------------------------------------------------
# Shortlist
# ---------------------------------------------------------------------------

@router.get("/{student_id}/shortlist", response_model=ShortlistResponse)
async def get_shortlist(
    student_id: int,
    counselor_id: int = Depends(get_current_counselor_id),
):
    def _query():
        conn = get_conn()
        try:
            if not _owns(conn, student_id, counselor_id):
                return None
            rows = conn.execute(
                "SELECT * FROM student_shortlists WHERE student_id = ? ORDER BY id",
                (student_id,),
            ).fetchall()
            return [_shortlist_item(r) for r in rows]
        finally:
            conn.close()

    items = await asyncio.to_thread(_query)
    if items is None:
        raise HTTPException(404, f"Student {student_id} not found")
    return ShortlistResponse(student_id=student_id, items=items)


@router.post("/{student_id}/shortlist", response_model=ShortlistResponse)
async def save_shortlist(
    student_id: int,
    body: ShortlistRequest,
    counselor_id: int = Depends(get_current_counselor_id),
):
    def _replace():
        conn = get_conn()
        try:
            if not _owns(conn, student_id, counselor_id):
                return None
            conn.execute(
                "DELETE FROM student_shortlists WHERE student_id = ?", (student_id,)
            )
            for item in body.items:
                conn.execute(
                    """INSERT INTO student_shortlists
                       (student_id, canonical_code, college_name, branch_name, band,
                        predicted_close, margin, confidence, category_used, seat_type,
                        fee_text, branch_code, college_score, seat_pool)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        student_id, item.canonical_code, item.college_name,
                        item.branch_name, item.band, item.predicted_close,
                        item.margin, item.confidence, item.category_used,
                        item.seat_type, item.fee_text, item.branch_code,
                        item.college_score, item.seat_pool,
                    ),
                )
            conn.commit()
            rows = conn.execute(
                "SELECT * FROM student_shortlists WHERE student_id = ? ORDER BY id",
                (student_id,),
            ).fetchall()
            return [_shortlist_item(r) for r in rows]
        finally:
            conn.close()

    items = await asyncio.to_thread(_replace)
    if items is None:
        raise HTTPException(404, f"Student {student_id} not found")
    return ShortlistResponse(student_id=student_id, items=items)
