"""
EduPath — Counsellor preference-list tool (Phase 5 UI).

Run from the project root:
    streamlit run app/streamlit_app.py

Talks ONLY to engine_adapter (the contract boundary). The engine's data realities
are surfaced honestly: missing fees show "Fee N/A" (never Rs 0), low-confidence
predictions are badged, and an unresolved home district is warned about.
"""
import os
import sys
import html

import pandas as pd
import streamlit as st

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import engine_adapter as ea  # noqa: E402
import shortlist_utils  # noqa: E402

st.set_page_config(page_title="EduPath — CAP Preference Builder",
                   page_icon="🎓", layout="wide")

# ── Cached engine calls (Streamlit reruns the whole script each interaction) ──
@st.cache_data(show_spinner=False)
def cached_preference(percentile, category_label, district, branches, budget, rnd):
    return ea.preference_list(percentile, category_label, district,
                              branch_preferences=list(branches) or None,
                              fee_budget=budget, round_num=rnd)

@st.cache_data(show_spinner=False)
def cached_strategy(percentile, category_label, district, branches):
    return ea.round_strategy(percentile, category_label, district,
                             branch_preferences=list(branches) or None)

@st.cache_data(show_spinner=False)
def cached_profile(code):
    return ea.college_profile(code)


# ── Session state ────────────────────────────────────────────────────────────
st.session_state.setdefault("results", None)
st.session_state.setdefault("inputs", None)
st.session_state.setdefault("shortlist", {})   # canonical_code -> row dict


# ── Small render helpers ─────────────────────────────────────────────────────
SEAT_COLOR = {"Home": "blue", "Other": "grey", "State": "violet"}
CONF_COLOR = {"high": "green", "medium": "orange", "low": "red"}


def fee_text(fee):
    return f"Rs {fee['total_annual']:,}/yr" if fee.get("available") else "Fee N/A"


def _e(s):
    return html.escape(str(s)) if s is not None else "—"


def build_printable(inp, data, shortlist):
    """Self-contained, print-styled HTML the counsellor downloads and prints (Ctrl+P)."""
    rows = "".join(
        f"<tr><td class='n'>{i}</td><td><b>{_e(r['branch_name'])}</b><br>"
        f"<span class='c'>{_e(r['college_name'])}</span></td>"
        f"<td>{_e(r['seat_type'])}</td>"
        f"<td>{r['predicted_close']:.1f}%</td>"
        f"<td>{_e(r['confidence'])}</td>"
        f"<td>{_e(fee_text(r['fee']))}</td></tr>"
        for i, r in enumerate(shortlist, 1)
    )
    return f"""<!doctype html><html><head><meta charset="utf-8">
<title>CAP Preference List</title><style>
body{{font-family:Arial,sans-serif;margin:30px;color:#111}}
h1{{font-size:20px;margin:0 0 4px}} .sub{{color:#444;margin-bottom:16px}}
table{{border-collapse:collapse;width:100%}} th,td{{border:1px solid #999;padding:6px 8px;font-size:13px;text-align:left}}
th{{background:#f0f0f0}} td.n{{width:28px;text-align:center;font-weight:bold}}
.c{{color:#555;font-size:12px}}
.note{{margin-top:16px;font-size:12px;color:#666}}
@media print{{button{{display:none}}}}
</style></head><body>
<h1>CAP Preference List</h1>
<div class="sub">Percentile <b>{_e(inp['percentile'])}%</b> &middot; {_e(inp['category_label'])}
&middot; Home: {_e(data['home_district'])} &rarr; {_e(data['student_university_name'] or data['student_university'] or 'unresolved')}
&middot; CAP Round {_e(data['round_num'])}</div>
<table><thead><tr><th>#</th><th>Branch / College</th><th>Seat</th>
<th>2026 close (pred)</th><th>Confidence</th><th>Fee</th></tr></thead>
<tbody>{rows}</tbody></table>
<div class="note">Predicted closing percentiles are estimates from 2023&ndash;2025 CAP cutoff
trends, not guarantees. Enter these choices in the official CAP portal in this order.</div>
</body></html>"""


def add_to_shortlist(row):
    # Route single-card adds through the same dedupe path as table adds, so both
    # store identical row dicts keyed by canonical_code.
    shortlist_utils.dedupe_add(st.session_state.shortlist, [row])


def _seat_data_cell(row):
    """Compact seat-data signal for the table: ⚠ for fallback, ✓ otherwise, + code."""
    mark = "⚠" if row.get("seat_data_status") == "fallback" else "✓"
    return f"{mark} {row.get('category_used') or '—'}"


def render_band_table(rows, band_key):
    """
    Full-band sortable, multi-select table (replaces the card grid when 'View all'
    is on). Selected rows -> Add selected to shortlist. Renders headers even when
    the band is empty. Maps selection indices back to the SAME source row dicts the
    cards use, so table-add and card-add produce identical shortlist entries.
    """
    columns = ["College", "Branch", "Pred close", "Margin",
               "Confidence", "Seat data", "Fee", "Score"]
    if rows:
        table = pd.DataFrame([{
            "College": r["college_name"],
            "Branch": r["branch_name"],
            "Pred close": round(r["predicted_close"], 1),
            "Margin": round(r["margin"], 1),
            "Confidence": r["confidence"],
            "Seat data": _seat_data_cell(r),
            "Fee": fee_text(r["fee"]),
            "Score": r["college_score"],
        } for r in rows], columns=columns)
    else:
        table = pd.DataFrame(columns=columns)   # headers, no rows, no crash

    event = st.dataframe(
        table, hide_index=True, width="stretch", height=420,
        on_select="rerun", selection_mode="multi-row",
        key=f"tbl_{band_key}",
    )
    selected_idx = event.selection["rows"] if rows else []
    if st.button(f"Add selected to shortlist ({len(selected_idx)})",
                 key=f"addsel_{band_key}", type="secondary",
                 disabled=not selected_idx, width="stretch"):
        chosen = [rows[i] for i in selected_idx]
        shortlist_utils.dedupe_add(st.session_state.shortlist, chosen)
        st.rerun()


def render_row(row, band_key, idx, social_label):
    """One college option card inside a band column."""
    with st.container(border=True):
        # Some source branch_name values are concatenations of several branches;
        # cap the display to one readable line so a card never becomes a text wall.
        branch = row["branch_name"]
        if len(branch) > 55:
            branch = branch[:55].rstrip() + "…"
        st.markdown(f"**{branch}**")
        st.caption(row["college_name"])
        # Honest seat-data line (Fix C2): warn ONLY when the prediction had to fall
        # back to a State-level cutoff because no home/other cutoff exists here.
        status = row.get("seat_data_status")
        cu = row.get("category_used")
        if status == "fallback":
            exp = row.get("expected_category") or "home/other"
            st.markdown(
                f":orange[⚠ State-level data only — no home/other {social_label} "
                f"cutoff at this college]"
            )
            st.caption(f"using {cu} · fallback from {exp}")
        elif status == "exact":
            st.markdown(f":green[✓ {row['seat_type']}-{social_label} data ({cu})]")
        else:  # state_only (EWS/TFWS/PwD…) — no home/other concept, not a fallback
            st.markdown(f":green[✓ {social_label} seat ({cu})]")
        st.markdown(
            f"Close **{row['predicted_close']:.1f}%** "
            f"(margin {row['margin']:+.1f}) · "
            f":{CONF_COLOR.get(row['confidence'],'grey')}[{row['confidence']} conf]"
        )
        st.markdown(f"💰 {fee_text(row['fee'])}  ·  📍 {row['city'] or '—'}")
        c1, c2 = st.columns(2)
        if c1.button("View college", key=f"view_{band_key}_{idx}", width='stretch'):
            show_college_dialog(row["college_code"])
        added = row["canonical_code"] in st.session_state.shortlist
        if c2.button("✓ Shortlisted" if added else "Add to shortlist",
                     key=f"add_{band_key}_{idx}", type="secondary",
                     disabled=added, width='stretch'):
            add_to_shortlist(row)
            st.rerun()


@st.dialog("College profile", width="large")
def show_college_dialog(code):
    p = cached_profile(code)
    if "error" in p:
        st.error(p["error"]); return
    st.subheader(p["college_name"])
    a, l = p["accreditation"], p["location"]
    st.markdown(
        f"**Type:** {p['identity']['institution_type'] or '—'} · "
        f"**Est:** {p['identity']['year_established'] or '—'} · "
        f"**Autonomous:** {'Yes' if p['identity']['is_autonomous'] else 'No'}  \n"
        f"**University:** {l['affiliated_university'] or '—'} · "
        f"**District:** {l['district'] or '—'}  \n"
        f"**NAAC:** {a['naac_grade'] or '—'} · **NIRF:** {a['nirf_rank'] or '—'} · "
        f"**Quality score:** {p['score']['overall'] or '—'}/100"
    )

    # Photos
    imgs = [im["url"] for im in p.get("images", []) if im.get("url")]
    if imgs:
        st.image(imgs[:6], width=210)

    # Fees by category. Collapse to one line ONLY when EVERY category is N/A; if
    # even one has real data, keep the full table so partial data stays visible.
    st.markdown("**Annual fee by category**")
    if not any(fee.get("available") for fee in p["fees"].values()):
        st.caption("Fee data unavailable — check with college.")
    else:
        fee_rows = []
        for cat, fee in p["fees"].items():
            fee_rows.append({"Category": cat,
                             "Annual fee": fee_text(fee),
                             "Basis": fee.get("fee_class") or fee.get("reason") or "—"})
        st.dataframe(fee_rows, hide_index=True, width='stretch')

    # Facilities
    f = p["facilities"]
    def yn(v): return "Yes" if v else "—"
    st.markdown(
        f"**Facilities** — Hostel (B/G): {yn(f['hostel_boys'])}/{yn(f['hostel_girls'])} · "
        f"WiFi: {yn(f['wifi'])} · Sports: {yn(f['sports'])}"
    )

    # Cutoff trends
    trends = p.get("cutoff_trends", [])
    if trends:
        st.markdown("**Cutoff trends — open seats (closing %)**")
        table = [{"Branch": t["branch_name"],
                  "2023": t["close_2023"], "2024": t["close_2024"],
                  "2025": t["close_2025"], "2026 (pred)": t["pred_2026"]}
                 for t in trends]
        st.dataframe(table, hide_index=True, width='stretch', height=260)


# ── Sidebar: student intake ──────────────────────────────────────────────────
with st.sidebar:
    st.title("🎓 EduPath")
    st.caption("CAP preference-list builder for counsellors")
    with st.form("intake"):
        percentile = st.number_input("MHT-CET percentile", 0.0, 100.0, 90.0, 0.1)
        category_label = st.selectbox("Category (seat pool)", ea.category_labels())
        district = st.selectbox("Home district", ea.district_options())
        st.caption("Select 'Other / Not listed' for out-of-state or All-India candidates.")
        branches = st.multiselect("Preferred branch(es)", ea.list_branch_keywords(),
                                  help="Leave empty to see all branches")
        budget_k = st.number_input("Max annual fee (Rs, 0 = no limit)",
                                   0, 1_000_000, 0, 5000)
        rnd = st.selectbox("CAP round", [1, 2, 3, 4], index=0)
        submitted = st.form_submit_button("Generate preference list",
                                          type="primary", width='stretch')
    if st.session_state.shortlist:
        st.divider()
        st.metric("Shortlisted", len(st.session_state.shortlist))

if submitted:
    budget = budget_k if budget_k > 0 else None
    # 'Other / Not listed' -> None for the engine; keep the label for display.
    district_arg = ea.resolve_district_input(district)
    st.session_state.inputs = dict(percentile=percentile, category_label=category_label,
                                   district=district_arg, district_label=district,
                                   branches=tuple(branches), budget=budget, rnd=rnd)
    st.session_state.results = cached_preference(
        percentile, category_label, district_arg, tuple(branches), budget, rnd)


# ── Main area ────────────────────────────────────────────────────────────────
data = st.session_state.results
if not data:
    st.title("CAP Preference Builder")
    st.info("Enter the student's details in the sidebar and click "
            "**Generate preference list** to begin.")
    st.stop()

if "error" in data:
    st.error(data["error"]); st.stop()

inp = st.session_state.inputs
st.title("Preference list")
university_display = (data["student_university_name"]
                      or data["student_university"] or "unresolved")
st.markdown(
    f"**{inp['percentile']}%** · {inp['category_label']} · "
    f"Home: {inp['district_label']} → "
    f"**{university_display}** · CAP Round {data['round_num']}"
)
if data["district_unresolved"]:
    st.warning("Home district could not be matched to a university — every college is "
               "treated as **Other** (no Home-seat advantage). Check the district spelling.")

tab_pref, tab_round, tab_short = st.tabs(
    ["📋 Preference list", "⏱️ Round strategy", f"⭐ Shortlist ({len(st.session_state.shortlist)})"])

# --- Preference list tab: three bands ---
with tab_pref:
    if not (data["safe"] or data["probable"] or data["reach"]):
        st.warning(
            "No matching options for this profile. This usually means: (a) no "
            "college in your filter set offers this branch, (b) historical "
            "cutoffs for this category at these colleges are not in our data, "
            "or (c) your budget/branch filters are too narrow. Try widening "
            "branch or removing the city filter."
        )
    # Budget honesty banner (Fix M2): counts verified-fee vs N/A across ALL results
    # (every band, before the 10-cap). Guarded against the zero-results case so it
    # never divides/odd-phrases on an empty set.
    if inp["budget"]:
        all_results = data["safe"] + data["probable"] + data["reach"]
        n_total = len(all_results)
        if n_total > 0:
            n_with_fee = sum(1 for r in all_results if r["fee"].get("available"))
            budget_l = f"{inp['budget'] / 100000:g}"
            st.info(
                f"Budget ₹{budget_l}L applied. {n_with_fee} of {n_total} results "
                f"have verified fee data — the rest are shown with 'Fee N/A' because "
                f"we don't yet have their fee on record. Verify fees with the college "
                f"directly before finalising."
            )
    cols = st.columns(3)
    bands = [("SAFE", "safe", "🟢"), ("PROBABLE", "probable", "🟡"), ("REACH", "reach", "🔴")]
    # Short social-category label for the per-card seat-data line (e.g. "SC", "Open").
    social_label = inp["category_label"].split("—")[-1].strip()
    for col, (title, key, dot) in zip(cols, bands):
        with col:
            rows = data[key]
            # A band holds one row per branch; many branches belong to the same
            # college. Show BOTH counts so the counsellor isn't misled into reading
            # branch-rows as colleges (Bug 2).
            branch_rows = len(rows)
            unique_colleges = len({r["college_code"] for r in rows})
            st.subheader(f"{dot} {title}")
            st.markdown(f"**{branch_rows} branches across {unique_colleges} colleges**")
            st.caption({"safe": "Comfortably above the predicted cutoff",
                        "probable": "Around the line — realistic",
                        "reach": "Below cutoff but within striking distance"}[key])
            # Per-band view toggle (independent of the other bands). Cards (top 10)
            # by default; table (sortable, multi-select, all rows) when expanded.
            view_all = False
            if branch_rows > 10:
                view_all = st.toggle(f"View all {branch_rows} branches",
                                     key=f"viewall_{key}")
            if not rows:
                # Empty REACH for a clearly strong profile means "no stretch left",
                # NOT "no data". Only say so when SAFE is solid (>=5); otherwise the
                # empty band genuinely means missing options — keep the neutral copy.
                if key == "reach" and len(data["safe"]) >= 5:
                    st.caption("Nothing is a stretch for this profile — "
                               "you're already targeting the top tier.")
                else:
                    st.caption("_No options in this band._")
            elif view_all:
                st.caption(f"All {branch_rows} branches — sort by any column, "
                           "tick rows, then Add selected.")
                render_band_table(rows, key)
            else:
                st.caption(f"Showing top {min(10, branch_rows)} of {branch_rows} branches")
                for i, row in enumerate(rows[:10]):
                    render_row(row, key, i, social_label)

# --- Round strategy tab ---
with tab_round:
    st.caption("Should the student lock a seat in Round 1, or wait for a later round "
               "where the cutoff typically drops?")
    rs = cached_strategy(inp["percentile"], inp["category_label"],
                         inp["district"], inp["branches"])
    ADVICE_ICON = {"lock_r1": "🔒", "wait_r3": "⏳", "watch_r1": "👀",
                   "hold_r1": "✋", "reach_late": "🎯", "unlikely": "🚫", "no_data": "❔"}
    results = rs["results"]
    if not results:
        st.info("No eligible branches to advise on for this student.")
    else:
        ACTIONABLE = ("wait_r3", "lock_r1", "watch_r1")
        show_all = st.checkbox("Show all strategies", value=False, key="round_show_all")
        actionable = [r for r in results if r["advice_code"] in ACTIONABLE]
        if show_all:
            shown = results
        else:
            shown = actionable if actionable else results
        if show_all:
            st.caption(f"Showing all {len(shown)} of {len(results)} predictions.")
        else:
            st.caption(
                f"Showing {len(shown)} of {len(results)} predictions, filtered to "
                f"actionable advice (wait_r3 / lock_r1 / watch_r1). "
                f"Tick 'Show all strategies' to see all."
            )
        table = [{
            " ": ADVICE_ICON.get(r["advice_code"], ""),
            "Branch": r["branch_name"], "College": r["college_name"],
            "Seat": r["seat_type"],
            "R1": r["r1_close"], "R3": r["r3_close"], "Drop": r["drop"],
            "Advice": r["advice"],
        } for r in shown]
        st.dataframe(
            table, hide_index=True, width='stretch', height=560,
            column_config={  # wide text columns -> table scrolls horizontally, names stay readable
                "Branch": st.column_config.TextColumn(width="large"),
                "College": st.column_config.TextColumn(width="large"),
                "Advice": st.column_config.TextColumn(width="large"),
            },
        )

# --- Shortlist & export tab ---
with tab_short:
    sl = list(st.session_state.shortlist.values())
    if not sl:
        st.info("Add colleges from the Preference list tab to build the student's "
                "ordered CAP preference list.")
    else:
        st.caption("This is the order the student will enter in the official CAP portal. "
                   "Remove any row, then download the printable list.")
        for i, row in enumerate(sl, 1):
            cc = st.columns([0.5, 6, 2, 2, 1])
            cc[0].markdown(f"**{i}.**")
            cc[1].markdown(f"**{row['branch_name']}** — {row['college_name']}")
            cc[2].markdown(f":{SEAT_COLOR.get(row['seat_type'],'grey')}[{row['seat_type']}]")
            cc[3].markdown(fee_text(row["fee"]))
            if cc[4].button("✕", key=f"rm_{i}", help="Remove"):
                del st.session_state.shortlist[row["canonical_code"]]
                st.rerun()
        st.divider()
        # Pre-export validation summary (display only, non-blocking). Only shown
        # when the shortlist is non-empty, so it never reads "0 of 0".
        flags = shortlist_utils.flag_counts(sl)
        if any(flags.values()):
            st.warning(
                f"Review before finalising: {flags['fallback']} use state-level "
                f"fallback data · {flags['low_confidence']} are low-confidence · "
                f"{flags['fee_na']} have no fee on record."
            )
        else:
            st.success("All shortlisted choices have exact seat data, solid "
                       "confidence, and a fee on record.")
        html_doc = build_printable(inp, data, sl)
        st.download_button("⬇️ Download printable list (HTML)", html_doc,
                           file_name="cap_preference_list.html",
                           mime="text/html", type="primary")
        st.caption("Open the downloaded file and print (Ctrl+P) to give the student a hard copy.")
