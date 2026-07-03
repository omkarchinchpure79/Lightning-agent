# EduPath — Lightning Agent

## Overview
Counsellor-facing AI agent for MHT CET CAP (Centralised Admission Process), Maharashtra, India.
Predicts college seat allotment probability from historical cutoff data. Helps counsellors build optimal preference lists.
**Users: counsellors (not students directly). Business: B2B2C via coaching partners.**

## Tech Stack
- Python 3.14, SQLite (local file: `db/edupath.db`)
- PDF parsing: `pdfplumber`
- No cloud — everything local. Budget: ₹3-5K total.

## Project Structure
```
data/raw/pdfs/         → Downloaded official CET Cell cutoff PDFs
data/processed/        → Intermediate parsed CSV/JSON before DB load
data/flagged/          → Rows that failed validation (human review queue)
scripts/               → Python pipeline scripts
db/                    → SQLite database (edupath.db)
tests/                 → Validation and spot-check tests
docs/                  → Reference docs, category legends, URL patterns
```

## Data Rules — CRITICAL
- Primary keys = **official numeric codes** (institute code, branch code). NEVER use text names.
- Validation gates (fail-closed — reject, never guess):
  - `category_count == pair_count` (no silent zip truncation)
  - `0.0 <= percentile <= 100.0`
  - Category code must exist in known legend
  - Institute code must exist in master list
- Failed rows → `flagged_reviews` table. NEVER auto-promote to live tables.
- Source: Official CET Cell PDFs only (`fe{year+1}.mahacet.org`)
- Data years: **2023, 2024, 2025** (3 years × 3-4 rounds = ~9-12 PDFs)
- **NO individual student data** (names, application IDs) — privacy policy, DPDP Act.

## Key Domain Concepts
- **CAP Round**: Centralised admission round (I, II, III + institutional)
- **Cutoff**: Closing percentile for college × branch × category × seat-type
- **Seat types**: H=Home University, O=Other, S=State Level, AI=All India
- **Categories**: GOPENS, GSCS, GSTS, GOBCS, GVJS, GNT1S, GNT2S, GNT3S, GEWS, TFWS, LOPENS, LSCS, LSTS, LOBCS, etc.
  - G=General, L=Ladies | H=Home, O=Other, S=State, AI=All India
  - PWDR=PwD reserved, DEFR=Defense reserved
- **College Score**: 0-100 quality scale (cutoff level, city tier, infra, accreditation, placements)

## PDF URL Pattern
Refer to [url_patterns.md](file:///C:/Lighting%20agent%20VS%20code/docs/url_patterns.md) for details. 2023 uses direct static PDFs, while 2024 and 2025 use base64-encoded PDFs embedded in `ViewPublicDocument.aspx?MenuId=XXXX`.

## Commands
```bash
python scripts/download_pdfs.py          # Download all CET Cell cutoff PDFs
python scripts/parse_cutoffs.py          # Parse PDFs → structured data with validation
python scripts/load_db.py               # Load validated data → edupath.db
python scripts/check_flagged.py         # Review items that failed validation
python scripts/predict.py --percentile 88.0 --category GOPENS  # Predict seat allotment
python scripts/predict.py --percentile 72.0 --category GSCS --city Pune --branch "Computer" --show-cutoffs
python -m unittest discover -s tests     # Run all validation + prediction-engine tests
streamlit run app/streamlit_app.py       # Phase 5 counsellor UI (needs `pip install streamlit`)
```

## Phase 5 — Counsellor UI (Streamlit)
- `streamlit run app/streamlit_app.py` — launch the counsellor tool in a browser.
- `app/engine_adapter.py` is the ONLY bridge between UI and engine: pins an absolute
  DB path (so the app runs from any cwd), maps category labels → base codes, sources
  dropdowns from the DB, wraps the four engine calls. The UI imports only this, never
  the engine directly. Tested in `tests/test_engine_adapter.py`.
- Surfaces engine realities honestly: missing fees show "Fee N/A" (never Rs 0),
  low-confidence predictions are badged, unresolved home district is warned.
- Export = self-contained print-friendly HTML via `build_printable` (counsellor
  prints with Ctrl+P). No PDF dependency.

## Verification Gate — RUN AFTER ANY SCRIPT CHANGE (non-negotiable)
Reviewing code by reading is NOT enough — three review passes still shipped bugs
(e.g. a half-finished refactor left predict.py un-importable). After editing ANY
script in `scripts/`, run this full gate and confirm it passes before calling done:
```bash
python scripts/setup_college_profiles.py     # apply schema/migrations + paired-code score sync
python scripts/populate_university_map.py     # university_code backfill + missing college_details stubs (seat-eligibility prereq)
python scripts/apply_data_corrections.py      # COEP/ICT fixes, district-from-name fixes, impossible-percentile quarantine
python scripts/generate_predictions.py        # regenerate predictions (carry-forward model)
python -m unittest discover -s tests          # 71 tests: data + engine + API + app cold-load must all pass
```
- Schema for `predictions_2026` lives ONLY in `constants.ensure_predictions_table` —
  never inline a second `CREATE TABLE` for it (that duplication caused the canonical_code bug).
- `CATEGORY_FALLBACKS`, `YEAR_WEIGHTS`, `canonical_branch_key` live ONLY in `constants.py`.
- Phase 4 seat-eligibility logic (`DISTRICT_ALIASES`, `CITY_TO_DISTRICT`,
  `BASE_CATEGORY_VARIANTS`, band thresholds, `resolve_seat_category`,
  `normalize_district`) lives ONLY in `constants.py`. `university_code` is
  required by the engine tests, so `populate_university_map.py` MUST run before them.
- **Prediction model is carry-forward, NOT trend extrapolation** (audit 2026-07-02):
  `predicted_pct` = latest year's closing. Backtest on 27,772 groups showed linear
  extrapolation is 44% worse MAE (13.5 vs 8.3). `trend_slope` is display metadata
  only. NEVER reintroduce extrapolation without `python scripts/backtest_predictions.py`
  proving it wins on held-out data. Probability sigmoid in `predict.py` is calibrated
  (k=0.25, clamp 7–93%) against actual 2025 outcomes — same rule applies.

## Phase 4 — Counsellor Engine (the engine room)
- `preference_engine.py` — ranked SAFE/PROBABLE/REACH list. Resolves Home/Other/State
  seat eligibility PER COLLEGE (student's home university vs the college's university);
  `predict.py` does NOT do this. Bands on margin = student_pct − predicted_close_R1:
  SAFE ≥+3 (conf≠low), PROBABLE −1..+3, REACH −4..−1, below −4 excluded. Ranked within
  band by predicted cutoff desc (selectivity), NOT margin.
- `cap_round_strategy.py` — lock-vs-wait from the R1→R3 predicted drop. Guards against
  sparse-data noise: drops >20 pts are treated as artifacts, not real cascades.
- `college_card_api.py` — `get_college_profile(code)`: identity, accreditation, fees by
  category, score breakdown, images, cutoff trends 2023→2026.
- `fee_calculator.py` — FRA per-category fee or explicit "unavailable" (NEVER ₹0). Only
  ~28/376 colleges have fee data today; the rest fail-explicit.
- Design rationale: [docs/phase4_design.md](docs/phase4_design.md).

## Known Data Quirks
- **College code format change (2023→2024)**: CET Cell changed from 4-digit (e.g. `3012`) to 5-digit (e.g. `03012`) college codes in 2024. The same physical college appears under different codes (and branch codes) across years. `predict.py` handles this by joining on college_name + branch_name, not branch_code.
- **AI quota rows**: Each AI row in `cutoffs` is one individual student allotment, not a per-branch cutoff. AI cutoff = MIN(percentile) per branch/year/round.
- **Category code spaces**: Parser can produce garbled category codes with spaces (`AI MI`, `AI AI AI...`) for edge-case PDF rows. `load_db.py` now rejects these before insert.
- **Impossible percentiles in official PDFs**: CET Cell's own PDFs contain rows whose printed percentile is impossible for the printed merit number (65 TFWS rows printed `(0.0000000)` against merits like 1102 — verified against source). `constants.find_impossible_percentile_keys` (within-year monotonicity test) gates these at load time and `apply_data_corrections.py` quarantines them from a live DB. NOTE: naive cohort-size bounds do NOT work — 2023's merit-list bottom (~143k) legitimately closes at 0.0x percentile.
- **Dead codes**: canonical branch keys last seen in 2023 cannot be chosen in current CAP (2024 re-numbering). `generate_predictions.py` skips them (`MIN_LATEST_DATA_YEAR`).

## Naming
- Files/folders: snake_case
- DB tables/columns: snake_case
- Python: PEP 8

## Verification Checklist
1. `flagged_reviews` table is empty or all items reviewed
2. Random spot-check: 50 rows vs source PDF by eye
3. Cross-check known colleges (COEP, VJTI, PICT) against published cutoffs
4. Row counts per college-branch match expected category count
