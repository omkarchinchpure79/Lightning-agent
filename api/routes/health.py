import asyncio

from fastapi import APIRouter

from api.db import DB_PATH, get_conn
from api.schemas import HealthResponse

import engine_adapter  # noqa: F401 — import confirms engine is reachable

router = APIRouter()


@router.get("/health", response_model=HealthResponse)
async def health():
    def _counts():
        conn = get_conn()
        try:
            college_count = conn.execute(
                "SELECT COUNT(DISTINCT college_name) FROM colleges"
            ).fetchone()[0]
            prediction_count = conn.execute(
                "SELECT COUNT(*) FROM predictions_2026"
            ).fetchone()[0]
            return college_count, prediction_count
        finally:
            conn.close()

    college_count, prediction_count = await asyncio.to_thread(_counts)
    return HealthResponse(
        status="ok",
        db_path=DB_PATH,
        college_count=college_count,
        prediction_count=prediction_count,
        engine_importable=True,
    )
