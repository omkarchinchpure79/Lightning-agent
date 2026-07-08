"""
schemas.py — Pydantic v2 request/response models for the EduPath FastAPI service.

All list fields (preferred_branches, preferred_locations) are Python lists in the
API layer; the DB layer serialises them as JSON text. Conversion happens in the
route handlers, not here.
"""
from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, Field, field_validator, model_validator


# ---------------------------------------------------------------------------
# Student CRUD
# ---------------------------------------------------------------------------

def _validate_category_base(v: Optional[str]) -> Optional[str]:
    """Fail-closed: reject unknown base categories at write time, not at
    prediction time — otherwise an invalid student sits in the DB and every
    later prediction call 400s. Lazy imports because api.db's import
    side-effect puts app/ on sys.path and engine_adapter puts scripts/ there.
    """
    if v is None:
        return v
    from api import db as _db  # noqa: F401
    import engine_adapter  # noqa: F401
    from constants import BASE_CATEGORY_VARIANTS

    code = v.strip().upper()
    if code not in BASE_CATEGORY_VARIANTS:
        valid = ", ".join(sorted(BASE_CATEGORY_VARIANTS))
        raise ValueError(f"Unknown base category '{v}'. Use one of: {valid}")
    return code


def _dse_supported_category(code: str) -> bool:
    """True if this base category has a seat quota in DSE (e.g. TFWS does not)."""
    from api import db as _db  # noqa: F401
    import engine_adapter  # noqa: F401
    from constants import DSE_CATEGORY_MAP

    return DSE_CATEGORY_MAP.get(code) is not None


class StudentCreate(BaseModel):
    name: str
    gender: Optional[str] = None
    # Required for admission_type='fe'; for 'dse' it mirrors diploma_pct
    # (the DB column is NOT NULL and list sorting uses it as the merit mark).
    percentile: Optional[float] = Field(None, ge=0.0, le=100.0)
    admission_type: str = "fe"
    diploma_pct: Optional[float] = Field(None, ge=0.0, le=100.0)
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
    ews_eligible: bool = False
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

    @field_validator("category_base")
    @classmethod
    def _valid_category_base(cls, v: str) -> str:
        return _validate_category_base(v)

    @model_validator(mode="after")
    def _admission_type_consistency(self) -> "StudentCreate":
        if self.admission_type not in ("fe", "dse"):
            raise ValueError("admission_type must be 'fe' or 'dse'")
        if self.admission_type == "fe":
            if self.percentile is None:
                raise ValueError("percentile is required for first-year (fe) students")
        else:
            if self.diploma_pct is None:
                raise ValueError("diploma_pct is required for direct-second-year (dse) students")
            if not _dse_supported_category(self.category_base):
                raise ValueError(
                    f"Category '{self.category_base}' has no seat quota in DSE "
                    f"(e.g. TFWS exists only in first-year CAP)")
            if self.percentile is None:
                self.percentile = self.diploma_pct  # NOT NULL mirror, see api/db.py
        return self


class StudentUpdate(BaseModel):
    """All fields optional — only provided fields are updated (PATCH semantics).
    Cross-field admission-type consistency (a 'dse' student must end up with a
    diploma_pct, etc.) is enforced in the PATCH route against the MERGED row,
    since a partial update can't be judged in isolation."""
    name: Optional[str] = None
    gender: Optional[str] = None
    percentile: Optional[float] = Field(None, ge=0.0, le=100.0)
    admission_type: Optional[str] = None
    diploma_pct: Optional[float] = Field(None, ge=0.0, le=100.0)
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
    ews_eligible: Optional[bool] = None
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

    @field_validator("category_base")
    @classmethod
    def _valid_category_base(cls, v: Optional[str]) -> Optional[str]:
        return _validate_category_base(v)

    @field_validator("admission_type")
    @classmethod
    def _valid_admission_type(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and v not in ("fe", "dse"):
            raise ValueError("admission_type must be 'fe' or 'dse'")
        return v


class StudentListItem(BaseModel):
    id: int
    name: str
    percentile: float
    admission_type: str = "fe"
    category_base: str
    home_district: Optional[str]
    updated_at: str


class StudentResponse(BaseModel):
    id: int
    name: str
    gender: Optional[str]
    percentile: float
    admission_type: str = "fe"
    diploma_pct: Optional[float] = None
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
    ews_eligible: bool = False
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
    branch_code: Optional[str] = None
    college_score: Optional[float] = None
    seat_pool: Optional[str] = None
    # Response-only, computed fresh on every GET (never sent by the client on
    # save, never stored) — the official CET Cell CAP option-form identity for
    # this entry: institute_code/choice_code are pure zero-padding of the
    # already-stored branch_code (stable college identity, not a prediction —
    # no staleness risk); university_name is a live join so it can't go stale
    # either. See api/routes/students.py::_attach_choice_code_fields.
    institute_code: Optional[str] = None
    choice_code: Optional[str] = None
    university_name: Optional[str] = None


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
    round_num: int = Field(1, ge=1, le=4)
    # Reserved-pool eligibility (C1): when set, the engine additionally surfaces
    # that pool's seats (e.g. TFWS) merged into the same SAFE/PROBABLE/REACH bands,
    # tagged with seat_pool. Mirrors student_profiles' stored flags so the ad-hoc
    # route can exercise the same pools as the student-linked route.
    tfws_eligible: bool = False
    defense_status: bool = False
    pwd_status: bool = False
    orphan_status: bool = False
    ews_eligible: bool = False
    family_income_bracket: Optional[str] = None


class StudentPredictionRequest(BaseModel):
    round_num: int = Field(1, ge=1, le=4)


# ---------------------------------------------------------------------------
# College search
# ---------------------------------------------------------------------------

class CollegeSearchResult(BaseModel):
    college_code: str
    college_name: str
    city: Optional[str]
    score: Optional[float]
    top_percentile: Optional[float] = None
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
