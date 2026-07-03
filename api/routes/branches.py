"""
branches.py — canonical_code branch deep-dive.

canonical_code is the stable cross-year branch identity (e.g. "CODE::12345"
or "NAME::COEP::Computer Science"). It collapses K/L/LK seat-sub-type
variants, so one entry covers all seat variants of the same physical branch.

Returns:
  - identity (college, branch, paired branch codes)
  - cutoff_trends: closing percentile 2023–2025 per category (representative
    open categories plus any available), grouped by year and round
  - predictions_2026: all predicted closes for all categories and rounds
"""
import asyncio

from fastapi import APIRouter, HTTPException

import engine_adapter  # noqa: F401  — puts scripts/ on sys.path for constants
from api.db import get_conn
from constants import canonical_branch_key

router = APIRouter()

OPEN_CATS = ("GOPENH", "GOPENS", "GOPENO")


def _history_branch_codes(conn, canonical_code, college_name):
    """
    Every cutoffs.branch_code that maps to this canonical branch — across ALL
    years. predictions_2026 only stores the most recent year's code (10-digit),
    but 2023 rows carry the un-padded 9-digit code, so filtering history by the
    prediction's codes silently dropped 2023 from every branch page.
    """
    if canonical_code.startswith("CODE::"):
        root = canonical_code[len("CODE::"):]
        cand = conn.execute(
            """SELECT DISTINCT cu.branch_code, b.branch_name, c.college_name
               FROM cutoffs cu
               JOIN branches b ON b.branch_code = cu.branch_code
               JOIN colleges c ON c.college_code = b.college_code
               WHERE LTRIM(cu.branch_code, '0') LIKE ?""",
            (root + "%",),
        ).fetchall()
    else:  # NAME::<frag>::<branch> canonicals (re-coded colleges, e.g. COEP)
        frag = canonical_code.split("::")[1]
        cand = conn.execute(
            """SELECT DISTINCT cu.branch_code, b.branch_name, c.college_name
               FROM cutoffs cu
               JOIN branches b ON b.branch_code = cu.branch_code
               JOIN colleges c ON c.college_code = b.college_code
               WHERE c.college_name LIKE ?""",
            (f"%{frag}%",),
        ).fetchall()
    return [
        r["branch_code"] for r in cand
        if canonical_branch_key(r["college_name"], r["branch_name"],
                                r["branch_code"]) == canonical_code
    ]


@router.get("/{canonical_code:path}")
async def branch_deep_dive(canonical_code: str):
    def _query():
        conn = get_conn()
        try:
            # Identity from predictions_2026 (any row for this canonical_code).
            id_row = conn.execute(
                """SELECT college_code, college_name, branch_name
                   FROM predictions_2026
                   WHERE canonical_code = ?
                   LIMIT 1""",
                (canonical_code,),
            ).fetchone()
            if not id_row:
                return None

            college_code = id_row["college_code"]
            college_name = id_row["college_name"]
            branch_name = id_row["branch_name"]

            # All branch_codes that map to this canonical_code across ALL
            # years (seat variants + the un-padded 2023 form).
            branch_codes = _history_branch_codes(conn, canonical_code, college_name)
            if not branch_codes:  # canonical exists only in predictions
                branch_codes = [
                    r[0]
                    for r in conn.execute(
                        "SELECT DISTINCT branch_code FROM predictions_2026 "
                        "WHERE canonical_code = ?",
                        (canonical_code,),
                    )
                ]
            bc_ph = ",".join("?" * len(branch_codes))

            # Historical cutoffs 2023–2025: closing percentile per year/round/category.
            hist_rows = conn.execute(
                f"""SELECT cu.year, cu.round, cu.category, MIN(cu.percentile) AS percentile
                    FROM cutoffs cu
                    WHERE cu.branch_code IN ({bc_ph})
                      AND cu.is_all_india = 0
                      AND cu.exam_type LIKE 'MHT-CET%'
                    GROUP BY cu.year, cu.round, cu.category
                    ORDER BY cu.year, cu.round, cu.category""",
                branch_codes,
            ).fetchall()

            # All 2026 predictions for this canonical_code.
            pred_rows = conn.execute(
                """SELECT round, category, predicted_pct, predicted_low, predicted_high,
                          confidence, trend_slope, years_used
                   FROM predictions_2026
                   WHERE canonical_code = ?
                   ORDER BY round, category""",
                (canonical_code,),
            ).fetchall()

            return {
                "canonical_code": canonical_code,
                "college_code": college_code,
                "college_name": college_name,
                "branch_name": branch_name,
                "branch_codes": branch_codes,
                "cutoff_trends": [
                    {
                        "year": r["year"],
                        "round": r["round"],
                        "category": r["category"],
                        "percentile": round(r["percentile"], 2),
                    }
                    for r in hist_rows
                ],
                "predictions_2026": [
                    {
                        "round": r["round"],
                        "category": r["category"],
                        "predicted_pct": round(r["predicted_pct"], 2),
                        "predicted_low": r["predicted_low"],
                        "predicted_high": r["predicted_high"],
                        "confidence": r["confidence"],
                        "trend_slope": r["trend_slope"],
                        "years_used": r["years_used"],
                    }
                    for r in pred_rows
                ],
            }
        finally:
            conn.close()

    result = await asyncio.to_thread(_query)
    if result is None:
        raise HTTPException(
            404,
            {"error": "Branch not found", "canonical_code": canonical_code},
        )
    return result
