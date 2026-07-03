"""
shortlist_utils.py — pure (no-Streamlit) helpers for the preference shortlist.

Kept separate from streamlit_app so the dedupe and pre-export-summary logic is
unit-testable without a Streamlit run context. The card "Add to shortlist" button
and the table "Add selected" button both route through dedupe_add(), so the two
paths store IDENTICAL row dicts and dedupe identically.
"""


def dedupe_add(shortlist, rows):
    """
    Add each row dict to `shortlist` (a dict keyed by canonical_code) without
    creating duplicates. Mutates `shortlist` in place; returns the number added.

    canonical_code is the stable per-physical-branch identity (it already collapses
    K/L/LK seat-sub-type variants), so it is the correct dedupe key and is exactly
    what the card-add path uses — card and table adds therefore behave identically.
    """
    added = 0
    for r in rows:
        key = r["canonical_code"]
        if key not in shortlist:
            shortlist[key] = r
            added += 1
    return added


def flag_counts(rows):
    """
    Count risky picks in the shortlist for the pre-export validation summary:
      - fallback       : prediction used a State-level cutoff (no home/other data)
      - low_confidence : single-year / noisy trend
      - fee_na         : no fee on record
    Pure display data; never blocks export.
    """
    return {
        "fallback": sum(1 for r in rows if r.get("seat_data_status") == "fallback"),
        "low_confidence": sum(1 for r in rows if r.get("confidence") == "low"),
        "fee_na": sum(1 for r in rows if not r["fee"].get("available")),
    }
