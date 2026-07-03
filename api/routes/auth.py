"""
auth.py — Counselor signup, login, and /me endpoints.

POST /api/auth/signup  — create account, return token
POST /api/auth/login   — verify password, return token
GET  /api/auth/me      — decode token, return counselor info
"""
import asyncio
import sqlite3

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from api.auth_utils import (
    create_token,
    get_current_counselor_id,
    hash_password,
    verify_password,
)
from api.db import get_conn

router = APIRouter()


class SignupRequest(BaseModel):
    name: str
    email: str
    password: str


class LoginRequest(BaseModel):
    email: str
    password: str


class AuthResponse(BaseModel):
    token: str
    counselor_id: int
    name: str
    email: str


class CounselorInfo(BaseModel):
    counselor_id: int
    name: str
    email: str
    created_at: str


@router.post("/signup", response_model=AuthResponse, status_code=201)
async def signup(body: SignupRequest):
    if not body.name.strip():
        raise HTTPException(400, "Name is required")
    if not body.email.strip() or "@" not in body.email:
        raise HTTPException(400, "Valid email is required")
    if len(body.password) < 8:
        raise HTTPException(400, "Password must be at least 8 characters")

    email = body.email.strip().lower()

    def _create():
        conn = get_conn()
        try:
            existing = conn.execute(
                "SELECT id FROM counselors WHERE LOWER(email) = ?", (email,)
            ).fetchone()
            if existing:
                raise HTTPException(409, "An account with this email already exists")
            pw_hash = hash_password(body.password)
            try:
                cur = conn.execute(
                    "INSERT INTO counselors (name, email, password_hash) VALUES (?, ?, ?)",
                    (body.name.strip(), email, pw_hash),
                )
            except sqlite3.IntegrityError:
                # lost a signup race on the UNIQUE(email) constraint
                raise HTTPException(409, "An account with this email already exists")
            conn.commit()
            return cur.lastrowid
        finally:
            conn.close()

    cid = await asyncio.to_thread(_create)
    token = create_token(cid, email)
    return AuthResponse(token=token, counselor_id=cid, name=body.name.strip(), email=email)


@router.post("/login", response_model=AuthResponse)
async def login(body: LoginRequest):
    email = body.email.strip().lower()

    def _fetch():
        conn = get_conn()
        try:
            return conn.execute(
                "SELECT id, name, email, password_hash FROM counselors WHERE LOWER(email) = ?",
                (email,),
            ).fetchone()
        finally:
            conn.close()

    row = await asyncio.to_thread(_fetch)
    if not row or not verify_password(body.password, row["password_hash"]):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid email or password")

    token = create_token(row["id"], row["email"])
    return AuthResponse(token=token, counselor_id=row["id"], name=row["name"], email=row["email"])


@router.get("/me", response_model=CounselorInfo)
async def get_me(counselor_id: int = Depends(get_current_counselor_id)):
    def _fetch():
        conn = get_conn()
        try:
            return conn.execute(
                "SELECT id, name, email, created_at FROM counselors WHERE id = ?",
                (counselor_id,),
            ).fetchone()
        finally:
            conn.close()

    row = await asyncio.to_thread(_fetch)
    if not row:
        raise HTTPException(404, "Counselor not found")
    return CounselorInfo(
        counselor_id=row["id"],
        name=row["name"],
        email=row["email"],
        created_at=row["created_at"],
    )
