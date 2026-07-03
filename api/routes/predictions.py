"""
predictions.py — ad-hoc predictions and student-linked predictions.

Both routes call engine_adapter.preference_list, which is the only gateway
to the prediction engine. The student-linked route reads the stored profile
and passes its fields to the engine — round_num can be overridden in the
request body.

Edge cases:
- home_district=None passes district=None to engine (out-of-state handling).
- preferred_branches=[] is treated as None (engine treats empty list differently
  from None: None disables the branch filter entirely).
"""
import asyncio
import json
from typing import Optional

from fastapi import APIRouter, Body, Depends, HTTPException

import engine_adapter as ea
from api.auth_utils import get_current_counselor_id
from api.db import get_conn
from api.schemas import AdHocPredictionRequest, StudentPredictionRequest

router = APIRouter()


def _parse_json_list(value) -> Optional[list]:
    if not value:
        return None
    try:
        lst = json.loads(value)
        return lst if lst else None
    except (json.JSONDecodeError, TypeError):
        return None


@router.post("/predictions")
async def ad_hoc_prediction(body: AdHocPredictionRequest):
    result = await asyncio.to_thread(
        ea.preference_list,
        body.percentile,
        body.category_label,
        body.home_district,
        body.branch_preferences or None,
        body.fee_budget,
        body.round_num,
        None,                              # top_per_band
        body.preferred_locations or None,  # preferred_locations
        body.tfws_eligible,
        body.defense_status,
        body.pwd_status,
        body.orphan_status,
        body.family_income_bracket,
    )
    if "error" in result:
        raise HTTPException(400, result["error"])
    return result


@router.post("/students/{student_id}/predictions")
async def student_prediction(
    student_id: int,
    body: Optional[StudentPredictionRequest] = Body(default=None),
    counselor_id: int = Depends(get_current_counselor_id),
):
    round_num = body.round_num if body else 1

    def _fetch():
        conn = get_conn()
        try:
            row = conn.execute(
                "SELECT * FROM student_profiles WHERE id = ? AND counsellor_id = ?",
                (student_id, str(counselor_id)),
            ).fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

    student = await asyncio.to_thread(_fetch)
    if student is None:
        raise HTTPException(404, f"Student {student_id} not found")

    branches = _parse_json_list(student.get("preferred_branches"))
    locations = _parse_json_list(student.get("preferred_locations"))

    result = await asyncio.to_thread(
        ea.preference_list,
        student["percentile"],
        student["category_base"],   # pass code directly; adapter falls back to it
        student["home_district"],   # None if out-of-state
        branches,                   # None or non-empty list
        student.get("max_fee"),
        round_num,
        None,                       # top_per_band (unbounded)
        locations,                  # preferred_locations — None or non-empty list
        bool(student.get("tfws_eligible")),
        bool(student.get("defense_status")),
        bool(student.get("pwd_status")),
        bool(student.get("orphan_status")),
        student.get("family_income_bracket"),
    )
    if "error" in result:
        raise HTTPException(400, result["error"])
    return result
