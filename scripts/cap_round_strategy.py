"""
cap_round_strategy.py  (Phase 4 — Priority 2)

Lock-vs-wait advice. CAP cutoffs normally FALL from Round 1 to Round 3 (top
students vacate seats that cascade down), so a student just below the R1 close
may still get a seat in a later round. This module compares the student's
eligible R1 and R3 predicted closes per branch and advises.

IMPORTANT REALITY CHECK: our per-round predictions are fit independently on
sparse data, so the R1->R3 drop is NOT guaranteed positive (a noisy R3 can
predict HIGHER than R1). When that happens we do NOT recommend waiting on a
phantom drop — we flag the late-round data as unreliable and advise on R1 only.

Public API:
    get_round_strategy(percentile, base_category, home_district,
                       branch_preferences=None) -> dict
"""

import argparse
import sqlite3
import sys

from constants import BASE_CATEGORY_VARIANTS, resolve_seat_category
from preference_engine import resolve_student_university, _seat_label

DB_PATH = "db/edupath.db"

# Student is "comfortably in" if at least this far above the round close.
LOCK_BUFFER = 1.0
# A drop smaller than this is treated as noise (don't advise waiting on it).
MIN_MEANINGFUL_DROP = 0.5
# A drop larger than this is NOT a real round cascade — it's a sparse-data R3
# artifact (e.g. one low-percentile late allotment). Don't sell it as a wait.
MAX_CREDIBLE_DROP = 20.0


def _advise(percentile, r1, r3):
    """
    Return (advice_code, human_text) given the student's percentile and the
    eligible R1 / R3 predicted closes (either may be None).
    """
    if r1 is None and r3 is None:
        return "no_data", "No predicted cutoff for an eligible seat here."

    # Only one round has a prediction -> advise on what we have.
    if r1 is None:
        return ("reach_late", "Only late-round data; treat as a Round 3 target.")
    if r3 is None:
        if percentile >= r1 + LOCK_BUFFER:
            return "lock_r1", "Comfortably above the Round 1 close — lock it in Round 1."
        return "watch_r1", "Borderline at Round 1; no later-round data to fall back on."

    drop = r1 - r3  # positive = cutoff falls in later rounds (normal)

    # Already safe at the toughest (R1) close -> take it now, don't gamble.
    if percentile >= r1 + LOCK_BUFFER:
        return "lock_r1", "Safe at the Round 1 close — lock it in Round 1, no need to wait."

    # An implausibly large drop is sparse-data noise, not a real cascade.
    if drop > MAX_CREDIBLE_DROP:
        return ("hold_r1",
                f"Round 3 prediction ({r3:.1f}) looks like sparse-data noise "
                f"(drop ~{drop:.0f} pts isn't credible) — judge it on Round 1 only.")

    # Below R1 but the cutoff falls enough that R3 becomes reachable.
    if drop >= MIN_MEANINGFUL_DROP and percentile >= r3:
        return ("wait_r3",
                f"Below Round 1 (need {r1:.1f}) but the close drops ~{drop:.1f} pts by "
                f"Round 3 ({r3:.1f}) — realistic if you WAIT for a later round.")

    # Non-monotonic / negligible drop: late rounds don't help here.
    if drop < MIN_MEANINGFUL_DROP:
        return ("hold_r1",
                "Late-round cutoff isn't lower (noisy/limited data) — don't count on "
                "a later-round opening; judge it on Round 1.")

    return "unlikely", f"Below even the Round 3 close ({r3:.1f}) — unlikely in any round."


def _eligible_close(cats_by_round_cat, chain, round_num):
    """First close in the seat chain that has a prediction for this round."""
    for cat in chain:
        v = cats_by_round_cat.get((round_num, cat))
        if v is not None:
            return v, cat
    return None, None


def get_round_strategy(percentile, base_category, home_district,
                       branch_preferences=None):
    base_category = base_category.upper()
    variants = BASE_CATEGORY_VARIANTS.get(base_category)
    if not variants:
        return {"error": f"Unknown base category '{base_category}'."}
    candidate_cats = [c for c in variants if c]

    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA journal_mode=WAL")
    try:
        student_univ, univ_name, canon_district = \
            resolve_student_university(conn, home_district)
        placeholders = ",".join("?" * len(candidate_cats))
        rows = conn.execute(f"""
            SELECT p.canonical_code, p.college_code, p.college_name, p.branch_name,
                   p.round, p.category, p.predicted_pct, cd.university_code
            FROM predictions_2026 p
            JOIN college_details cd ON cd.college_code = p.college_code
            WHERE p.round IN (1,3) AND p.category IN ({placeholders})
        """, candidate_cats).fetchall()
    finally:
        conn.close()

    branches = {}
    for canon, ccode, cname, bname, rnd, cat, pred, univ in rows:
        g = branches.setdefault(canon, {
            "college_code": ccode, "college_name": cname, "branch_name": bname,
            "college_univ": univ, "by_round_cat": {},
        })
        g["by_round_cat"][(rnd, cat)] = pred

    out = []
    for canon, g in branches.items():
        chain = resolve_seat_category(base_category, student_univ, g["college_univ"])
        if not chain:
            continue
        r1, c1 = _eligible_close(g["by_round_cat"], chain, 1)
        r3, c3 = _eligible_close(g["by_round_cat"], chain, 3)
        if r1 is None and r3 is None:
            continue
        advice_code, text = _advise(percentile, r1, r3)
        out.append({
            "college_code": g["college_code"], "college_name": g["college_name"],
            "branch_name": g["branch_name"],
            "seat_type": _seat_label(c1 or c3, variants),
            "r1_close": r1, "r3_close": r3,
            "drop": round(r1 - r3, 2) if (r1 is not None and r3 is not None) else None,
            "advice_code": advice_code, "advice": text,
        })

    if branch_preferences:
        keys = [k.lower() for k in branch_preferences]
        out = [r for r in out if any(k in r["branch_name"].lower() for k in keys)]

    # Most actionable first: wait_r3 (a real opportunity), then lock_r1.
    order = {"wait_r3": 0, "lock_r1": 1, "watch_r1": 2, "hold_r1": 3,
             "reach_late": 4, "unlikely": 5, "no_data": 6}
    out.sort(key=lambda r: (order.get(r["advice_code"], 9),
                            -(r["r1_close"] or 0)))

    return {
        "percentile": percentile, "base_category": base_category,
        "home_district": home_district, "student_university": student_univ,
        "branch_preferences": branch_preferences, "results": out,
    }


def print_round_strategy(data, top=20):
    if "error" in data:
        print("ERROR:", data["error"]); return
    print(f"\n{'='*100}")
    print(f"  Round Strategy  |  {data['percentile']}%  |  {data['base_category']}  |  "
          f"{data['home_district']} -> {data['student_university'] or 'UNRESOLVED'}")
    print(f"{'='*100}")
    print(f"  {'Branch':<34} {'College':<26} {'Seat':<6} {'R1':>6} {'R3':>6} {'Drop':>6}  Advice")
    print("  " + "-"*112)
    for r in data["results"][:top]:
        r1 = f"{r['r1_close']:.1f}" if r["r1_close"] is not None else "-"
        r3 = f"{r['r3_close']:.1f}" if r["r3_close"] is not None else "-"
        dp = f"{r['drop']:+.1f}" if r["drop"] is not None else "-"
        print(f"  {r['branch_name'][:32]:<34} {r['college_name'][:24]:<26} "
              f"{r['seat_type']:<6} {r1:>6} {r3:>6} {dp:>6}  {r['advice'][:48]}")
    print()


def main():
    p = argparse.ArgumentParser(description="EduPath Phase 4 — CAP round lock/wait strategy.")
    p.add_argument("--percentile", type=float, required=True)
    p.add_argument("--category", type=str, required=True)
    p.add_argument("--district", type=str, required=True)
    p.add_argument("--branch", type=str, action="append", default=None)
    p.add_argument("--top", type=int, default=20)
    a = p.parse_args()
    data = get_round_strategy(a.percentile, a.category, a.district, a.branch)
    print_round_strategy(data, a.top)


if __name__ == "__main__":
    main()
