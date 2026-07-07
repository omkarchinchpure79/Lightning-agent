"""
dse_branches.py — canonical_code DSE branch deep-dive.

DSE twin of branches.py, but deliberately a SEPARATE route mounted at
/api/dse-branches (not reusing /api/branches/{code}) and querying ONLY
dse_cutoffs/dse_predictions. This is not just naming: FE's canonical_branch_key
and DSE's use the same key-generation function over different code registries
(FE branch_code vs DSE choice_code), so a shared endpoint keyed purely by
canonical_code string could in principle resolve a DSE-intended lookup against
FE's predictions_2026 table (or vice versa) if the two registries ever produced
the same stripped digit root for unrelated colleges. Keeping the two planes on
separate routes/tables removes that risk architecturally instead of relying on
the two ID spaces never colliding.

Rounds: DSE only publishes I-II (constants.DSE_VALID_ROUNDS) -- no III/IV.
"""
import asyncio

from fastapi import APIRouter, HTTPException

import engine_adapter  # noqa: F401  — puts scripts/ on sys.path for constants
from api.db import get_conn
from constants import canonical_branch_key

router = APIRouter()


@router.get("/{canonical_code:path}")
async def dse_branch_deep_dive(canonical_code: str):
    def _query():
        conn = get_conn()
        try:
            # Identity from dse_predictions (any row for this canonical_code).
            id_row = conn.execute(
                """SELECT college_code, college_name, branch_name
                   FROM dse_predictions
                   WHERE canonical_code = ?
                   LIMIT 1""",
                (canonical_code,),
            ).fetchone()

            college_code = college_name = branch_name = None
            if id_row:
                college_code, college_name, branch_name = (
                    id_row["college_code"], id_row["college_name"], id_row["branch_name"],
                )

            # All (college_code, choice_code) pairs that map to this canonical
            # branch across all years -- dse_cutoffs stores college_code/
            # college_name/course_name directly (no branches join, unlike FE).
            cand = conn.execute(
                "SELECT DISTINCT college_code, college_name, course_name, choice_code FROM dse_cutoffs"
            ).fetchall()
            matches = [
                r for r in cand
                if canonical_branch_key(r["college_name"], r["course_name"], r["choice_code"]) == canonical_code
            ]
            if not matches and not id_row:
                return None

            if matches and not id_row:
                college_code = matches[0]["college_code"]
                college_name = matches[0]["college_name"]
                branch_name = matches[0]["course_name"]

            choice_codes = sorted({m["choice_code"] for m in matches})
            cc_ph = ",".join("?" * len(choice_codes)) if choice_codes else None

            hist_rows = []
            if cc_ph:
                hist_rows = conn.execute(
                    f"""SELECT year, round, category, stage, MIN(merit_pct) AS merit_pct
                        FROM dse_cutoffs
                        WHERE choice_code IN ({cc_ph})
                        GROUP BY year, round, category
                        ORDER BY year, round, category""",
                    choice_codes,
                ).fetchall()

            pred_rows = conn.execute(
                """SELECT round, category, predicted_pct, predicted_low, predicted_high,
                          confidence, trend_slope, years_used
                   FROM dse_predictions
                   WHERE canonical_code = ?
                   ORDER BY round, category""",
                (canonical_code,),
            ).fetchall()

            if not hist_rows and not pred_rows:
                return None

            return {
                "canonical_code": canonical_code,
                "college_code": college_code,
                "college_name": college_name,
                "branch_name": branch_name,
                "choice_codes": choice_codes,
                "cutoff_trends": [
                    {
                        "year": r["year"],
                        "round": r["round"],
                        "category": r["category"],
                        "percentile": round(r["merit_pct"], 2),
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
            {"error": "DSE branch not found", "canonical_code": canonical_code},
        )
    return result
