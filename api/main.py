"""
main.py — EduPath FastAPI service entry point.

Start with:
    uvicorn api.main:app --reload --port 8000

CORS defaults to http://localhost:3000 (Next.js dev server). When deploying,
set CORS_ORIGINS to the deployed frontend origin(s), comma-separated.
"""
import api._seed_runtime  # noqa: F401  MUST be first — sets EDUPATH_DB_PATH on serverless

import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from api.db import init_tables
from api.routes import (
    auth,
    branches,
    colleges,
    counselor,
    dse_branches,
    health,
    lookups,
    predictions,
    students,
)

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_IMAGES_DIR = os.path.join(_ROOT, "data", "images")
try:
    os.makedirs(_IMAGES_DIR, exist_ok=True)
except OSError:
    # Read-only filesystem (serverless). Images aren't bundled there; serve an
    # empty dir from /tmp — the frontend falls back to placeholder art.
    _IMAGES_DIR = "/tmp/images"
    os.makedirs(_IMAGES_DIR, exist_ok=True)


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_tables()
    yield


app = FastAPI(
    title="EduPath API",
    description="MHT-CET CAP counselling engine — REST interface for the Next.js frontend.",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS_ORIGINS: comma-separated allowed frontend origins. Defaults to the local
# dev server; set to the deployed frontend URL in production
# (e.g. CORS_ORIGINS=https://edupath.example.com).
_cors_origins = [
    o.strip()
    for o in os.environ.get("CORS_ORIGINS", "http://localhost:3000").split(",")
    if o.strip()
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router,      prefix="/api",          tags=["health"])
app.include_router(auth.router,        prefix="/api/auth",     tags=["auth"])
app.include_router(lookups.router,     prefix="/api/lookups",  tags=["lookups"])
app.include_router(students.router,    prefix="/api/students", tags=["students"])
app.include_router(predictions.router, prefix="/api",          tags=["predictions"])
app.include_router(colleges.router,    prefix="/api/colleges", tags=["colleges"])
app.include_router(branches.router,    prefix="/api/branches", tags=["branches"])
app.include_router(dse_branches.router, prefix="/api/dse-branches", tags=["dse-branches"])
app.include_router(counselor.router,   prefix="/api/me",       tags=["counselor"])

# Locally-downloaded college campus photos (permanent replacement for hotlinked
# Google CDN images, which Chrome blocks once a Referer header is attached).
app.mount("/static/images", StaticFiles(directory=_IMAGES_DIR), name="images")
