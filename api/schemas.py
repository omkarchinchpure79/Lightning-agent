"""
schemas.py — Pydantic v2 request/response models for the EduPath FastAPI service.

All list fields (preferred_branches, preferred_locations) are Python lists in the
API layer; the DB layer serialises them as JSON text. Conversion happens in the
route handlers, not here.
"""
from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, Field, field_validator


# ---------------------------------------------------------------------------
# Student CRUD
# ---------------------------------------------------------------------------

class StudentCreate(BaseModel):
    name: str
    gender: Optional[str] = None
    percentile: float = Field(..., ge=0.0, le=100.0)
    jee_main_rank: Optional[int] = None
    board_pct: Optional[float] = None
    category_base: str
    category_variant: Optional[str] = None
    home_district: Optional[str] = None
    pwd_status: bool = False
    pwd_type: Optional[str] = None
    defense_status: bool = False
    tfws_eligible: bool = False
    orphan_status: bool = False
    family_income_bracket: Optional[str] = None
    preferred_branches: Optional[list[str]] = None
    preferred_locations: Optional[list[str]] = None
    max_fee: Optional[int] = None
    notes: Optional[str] = None
    counsellor_id: Optional[str] = None

    @field_validator("gender")
    @classmethod
    def _valid_gender(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and v not in ("M", "F", "Other"):
            raise ValueError("gender must be 'M', 'F', or 'Other'")
        return v


class StudentUpdate(BaseModel):
    """All fields optional — only provided fields are updated (PATCH semantics)."""
    name: Optional[str] = None
    gender: Optional[str] = None
    percentile: Optional[float] = Field(None, ge=0.0, le=100.0)
    jee_main_rank: Optional[int] = None
    board_pct: Optional[float] = None
    category_base: Optional[str] = None
    category_variant: Optional[str] = None
    home_district: Optional[str] = None
    pwd_status: Optional[bool] = None
    pwd_type: Optional[str] = None
    defense_status: Optional[bool] = None
    tfws_eligible: Optional[bool] = None
    orphan_status: Optional[bool] = None
    family_income_bracket: Optional[str] = None
    preferred_branches: Optional[list[str]] = None
    preferred_locations: Optional[list[str]] = None
    max_fee: Optional[int] = None
    notes: Optional[str] = None
    counsellor_id: Optional[str] = None

    @field_validator("gender")
    @classmethod
    def _valid_gender(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and v not in ("M", "F", "Other"):
            raise ValueError("gender must be 'M', 'F', or 'Other'")
        return v


class StudentListItem(BaseModel):
    id: int
    name: str
    percentile: float
    category_base: str
    home_district: Optional[str]
    updated_at: str


class StudentResponse(BaseModel):
    id: int
    name: str
    gender: Optional[str]
    percentile: float
    jee_main_rank: Optional[int]
    board_pct: Optional[float]
    category_base: str
    category_variant: Optional[str]
    home_district: Optional[str]
    pwd_status: bool
    pwd_type: Optional[str]
    defense_status: bool
    tfws_eligible: bool
    orphan_status: bool
    family_income_bracket: Optional[str]
    preferred_branches: Optional[list[str]]
    preferred_locations: Optional[list[str]]
    max_fee: Optional[int]
    notes: Optional[str]
    counsellor_id: Optional[str]
    created_at: str
    updated_at: str


# ---------------------------------------------------------------------------
# Shortlist
# ---------------------------------------------------------------------------

class ShortlistItem(BaseModel):
    canonical_code: str
    college_name: Optional[str] = None
    branch_name: Optional[str] = None
    band: Optional[str] = None
    predicted_close: Optional[float] = None
    margin: Optional[float] = None
    confidence: Optional[str] = None
    category_used: Optional[str] = None
    seat_type: Optional[str] = None
    fee_text: Optional[str] = None


class ShortlistRequest(BaseModel):
    items: list[ShortlistItem]


class ShortlistResponse(BaseModel):
    student_id: int
    items: list[ShortlistItem]


# ---------------------------------------------------------------------------
# Predictions
# ---------------------------------------------------------------------------

class AdHocPredictionRequest(BaseModel):
    percentile: float = Field(..., ge=0.0, le=100.0)
    category_label: str
    home_district: Optional[str] = None
    branch_preferences: Optional[list[str]] = None
    preferred_locations: Optional[list[str]] = None
    fee_budget: Optional[int] = None
    round_num: int = Field(1, ge=1, le=3)
    # Reserved-pool eligibility (C1): when set, the engine additionally surfaces
    # that pool's seats (e.g. TFWS) merged into the same SAFE/PROBABLE/REACH bands,
    # tagged with seat_pool. Mirrors student_profiles' stored flags so the ad-hoc
    # route can exercise the same pools as the student-linked route.
    tfws_eligible: bool = False
    defense_status: bool = False
    pwd_status: bool = False
    orphan_status: bool = False
    family_income_bracket: Optional[str] = None


class StudentPredictionRequest(BaseModel):
    round_num: int = Field(1, ge=1, le=3)


# ---------------------------------------------------------------------------
# College search
# ---------------------------------------------------------------------------

class CollegeSearchResult(BaseModel):
    college_code: str
    college_name: str
    city: Optional[str]
    score: Optional[float]
    district: Optional[str]
    institution_type: Optional[str]
    naac_grade: Optional[str] = None
    thumbnail_url: Optional[str] = None


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------

class HealthResponse(BaseModel):
    status: str
    db_path: str
    college_count: int
    prediction_count: int
    engine_importable: bool
