# Phase 4 Design — The Engine Room

Status: THINKING PHASE complete (Steps 1–5). Written before any engine code.

---

## STEP 1 — What we actually have vs what Phase 4 assumed

### Data that is REAL and solid (verified by query, not memory)
| Asset | State |
|---|---|
| `cutoffs` table | **241,874 rows**. Years 2023/2024/2025. Rounds: 2023→R1-3, 2024→R1-3, 2025→R1-4. |
| `seat_type` column | **Fully populated and rich.** Distinguishes Home/Other/State at the *seat* level (see below). |
| `predictions_2026` | **137,979 rows**, keyed by `canonical_code, category, round`. Linear-trend predicted close + slope + confidence. |
| `home_university_map` | **39 districts → 12 universities** (MU, SPPU, SUK, RTMNU, BAMU, SRTMUN, SGBAU, KBCNMU, SolU, …). Exists and is correct. |
| `colleges.city` | **379/379 populated.** Reliable. |
| `college_details.district` | 283/376 populated, but **DIRTY** (uppercase `PUNE`, sub-districts `Haveli Subdistrict`, `Mawal`, `Karvir`). Direct join to the univ map matches only **80/376**. |

### THE TWO CRITICAL MISMATCHES (flagged before building)

**MISMATCH #1 — Seat eligibility is NOT enforced anywhere today.**
`predict.py` takes a *fixed* category string (e.g. `GOPENH`) and applies it to **every college statewide**. That is wrong. A `GOPENH` (Home) seat at a Pune college is a "Home" seat **only for SPPU-jurisdiction students**. For a Nagpur student, that same Pune seat is an "Other" (`GOPENO`) seat. The category suffix H/O/S is meaningless until we know whether *this college* sits in *this student's* home university.

We have everything needed to fix it — `home_university_map` (student district→univ) and the college's own district — **but the link is broken**: see Mismatch #2.

**MISMATCH #2 — `college_details.university_code` is 0/376 (EMPTY).**
The column exists but was never populated. `affiliated_university` is also 0/376. Without this, the engine cannot tell which university a college belongs to, so it cannot resolve Home vs Other per college. **This is Priority 0 — a hard prerequisite for a correct preference list.** Fix path: normalize `district` (or fall back to `city`) → join `home_university_map` → write `university_code`.

**Fee gap (known, not a surprise):** `fee_tuition_open` 28/376 (7%), `tfws_available` 0/376. Step 4 handling applies.

---

## STEP 2 — Critical reasoning about the cutoff data

**1. Rounds.** Round 1 close > Round 3 close (top students leave seats that cascade down). The engine **predicts per-round** (predictions_2026 has a `round` column). Decision: the preference list is built on the **requested round (default R1)** because clearing R1 implies clearing all. R3 close is surfaced as the *floor* so a counsellor sees the realistic late-round opening. `cap_round_strategy.py` (Priority 2) uses the R1→R3 drop to advise lock-vs-wait.

**2. Sparsity.** ≤9 points per (college×branch×category×round) and often fewer. Already handled in `generate_predictions.linear_predict`: 3yr→high, 2yr→medium, 1yr→low; a linear extrapolation that lands outside [0,100] is downgraded to "low" and falls back to the latest actual close. The engine **never invents** a trend it doesn't have. Decision: **minimum 1 year** to appear at all, but `low` confidence is visually flagged and never classified `SAFE` (downgraded to `PROBABLE`).

**3. Trend direction.** `trend_slope` is stored. Negative slope = cutoff falling = easier next year. Surfaced per result so the counsellor sees direction, not just a point estimate.

**4. SAFE / PROBABLE / REACH — EXACT thresholds (locked, do not change mid-build).**
Let `m = student_pct − predicted_close_R1` (positive = student above the cutoff).
- **SAFE**: `m ≥ +3.0` — student is at least 3 percentile points clear of the predicted close. (Requires confidence ≠ low; a low-confidence SAFE is shown as PROBABLE.)
- **PROBABLE**: `−1.0 ≤ m < +3.0` — at or just around the line.
- **REACH**: `−4.0 ≤ m < −1.0` — below the R1 close but within striking distance (R2/R3 cutoffs drop, so this is genuinely reachable).
- **EXCLUDED**: `m < −4.0` — not realistic; omitted rather than shown as noise.
Asymmetry rationale: the 3-pt SAFE buffer absorbs prediction variance; REACH extends 4 pts *above* the student because later rounds fall.

**5. Seat-type logic (H / O / S) — the rule the engine enforces.**
Student supplies a **base category** (`GOPEN`, `GSC`, `GOBC`, `GVJ`, `GNT1/2/3`, `GSEBC`, `LOPEN`/Ladies variants…) + **home district**.
- Resolve student's `home_univ` = `home_university_map[home_district]`.
- For each college, resolve `college_univ` (Priority 0 data).
- If `college_univ == home_univ` → student is **HOME** here → evaluate against the **`…H`** cutoff, with **`…S`** (State) as the easier fallback.
- Else → student is **OTHER** here → evaluate against the **`…O`** cutoff, with **`…S`** fallback. **Never** offer this college's `…H` seats to an out-of-university student.
- State-only categories (`EWS`, `TFWS`, `DEFOPENS`, `PWD…`, `ORPHAN`) have no H/O split → eligible everywhere, evaluate against the `…S`/state code directly.
This is the single biggest correctness lever. The existing `CATEGORY_FALLBACKS` already encodes H→S and O→S chains; the engine adds the per-college H-vs-O *selection* that predict.py lacks.

---

## STEP 3 — What the counsellor needs (accuracy > breadth)
Input: percentile, base category, home district, branch preference(s), max fee budget.
Output per college×branch: name, branch, **seat type actually available to THIS student (H/O/S)**, predicted close, SAFE/PROBABLE/REACH band, fee estimate for the student's category (or explicit "fee unavailable"), confidence, trend. Plus a round-strategy note. One wrong row (wrong seat type, ₹0 fee, wrong direction) destroys trust → fail explicit, never silent.

## STEP 4 — Fee gap handling (locked)
- WITH fee data: total = category-adjusted tuition + development + fixed govt fees (FRA formula already designed).
- WITHOUT fee data (93%): **never return ₹0/null silently.** Budget filter splits results into "within budget", "over budget", and a clearly-labelled **"Fee data unavailable — not budget-filtered"** bucket. Missing fee never silently drops or passes a college.

---

## STEP 5 — Build order
- **Priority 0 — `populate_university_map.py`** (data prerequisite). Normalize district→canonical, fall back to city, write `college_details.university_code` for all paired codes. Verify coverage ≥ 95%.
- **Priority 1 — `preference_engine.py`**. seat-eligibility resolve → predicted close → SAFE/PROBABLE/REACH → fee filter → ranked JSON. Tested on ≥2 real student profiles.
- **Priority 2 — `cap_round_strategy.py`**. R1→R3 drop + percentile buffer → lock-vs-wait.
- **Priority 3 — `college_card_api.py`**. `get_college_profile(code)` → cutoff trends, fee breakdown, facilities, score.
- **Priority 4 — `fee_calculator.py`**. (college, category) → itemised total or "unavailable".
- **Priority 5 — confidence** integrated into Priority 1 output (from `predictions_2026.confidence` + years_used).

Shared logic (district normaliser, base-category↔H/O/S maps, band thresholds) lives in `constants.py` — single source of truth, per project rule.
