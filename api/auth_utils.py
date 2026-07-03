"""
auth_utils.py — JWT and bcrypt helpers for counselor authentication.

JWT secret is loaded from .env (JWT_SECRET).  Token payload: {sub: str(id), email: str}.
Passwords hashed with bcrypt (cost factor 12).
"""
import os
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

_security = HTTPBearer(auto_error=True)

_EXPIRE_DAYS = int(os.environ.get("JWT_EXPIRE_DAYS", "30"))
_ALGORITHM = "HS256"


def _secret() -> str:
    """
    Resolve JWT_SECRET at CALL time, never at import time. Two reasons:
    - import-order: api.db loads .env; a module importing auth_utils first
      would otherwise freeze an empty secret even though .env is fine.
    - fail-loud: signing/verifying with "" would make every token forgeable.
    """
    s = os.environ.get("JWT_SECRET", "")
    if not s:
        raise RuntimeError(
            "JWT_SECRET is not set (missing .env?) — refusing to sign or "
            "verify auth tokens with an empty secret.")
    return s


def hash_password(plain: str) -> str:
    return bcrypt.hashpw(plain.encode(), bcrypt.gensalt(rounds=12)).decode()


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(plain.encode(), hashed.encode())
    except Exception:
        return False


def create_token(counselor_id: int, email: str) -> str:
    exp = datetime.now(timezone.utc) + timedelta(days=_EXPIRE_DAYS)
    payload = {"sub": str(counselor_id), "email": email, "exp": exp}
    return jwt.encode(payload, _secret(), algorithm=_ALGORITHM)


def _decode_token(token: str) -> dict:
    try:
        return jwt.decode(token, _secret(), algorithms=[_ALGORITHM])
    except jwt.ExpiredSignatureError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid token")


def get_current_counselor_id(
    creds: HTTPAuthorizationCredentials = Depends(_security),
) -> int:
    """FastAPI dependency — returns counselor_id or raises 401."""
    payload = _decode_token(creds.credentials)
    return int(payload["sub"])
