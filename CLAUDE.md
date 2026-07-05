# EduPath — Lightning Agent

## Overview
Counsellor-facing AI agent for MHT CET CAP (Centralised Admission Process), Maharashtra, India.
Predicts college seat allotment probability from historical cutoff data. Helps counsellors build optimal preference lists.
**Users: counsellors (not students directly). Business: B2B2C via coaching partners.**

## Tech Stack
- Python 3.14, SQLite (local file: `db/edupath.db`)
- PDF parsing: `pdfplumber`
- API: FastAPI (`api/`) + JWT/bcrypt auth. Frontend: Next.js 16 / React 19 (`web/`)
- No cloud — everything local except optional Anthropic calls for AI college descriptions. Budget: ₹3-5K total.

## Project Structure
```
data/raw/pdfs/         → Downloaded official CET Cell cutoff PDFs
data/processed/        → Intermediate parsed CSV/JSON before DB load
data/flagged/          → Rows that failed validation (human review queue)
scripts/               → Python pipeline scripts (data pipeline + engine)
app/                   → engine_adapter.py — Streamlit UI bridge (Phase 5)
api/                   → FastAPI service (Phase 6) — REST interface for web/
web/                   → Next.js counsellor frontend (Phase 6)
db/                    → SQLite database (edupath.db) — shared by engine, API, and app
tests/                 → Validation, engine, API, and app tests (`python -m unittest`)
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

# Seat intake (one-time / periodic refresh, NOT part of the fast verification gate —
# downloads 368 PDFs and takes ~20-30 min to parse; re-run only when a new CAP round's
# seat matrix is published):
python scripts/download_seat_intake_pdfs.py   # CAPR-I seat-matrix PDFs, one per college
python scripts/parse_seat_intake.py           # -> branch_intake table (general/TFWS seats)

# Phase 6 — API + web (run from repo root / web/ respectively; needs .env with
# JWT_SECRET and, for AI college descriptions, ANTHROPIC_API_KEY — see .env.example):
python -m uvicorn api.main:app --reload --port 8000   # FastAPI backend
cd web && npm run dev                                  # Next.js frontend, port 3000 (dev only — see Turbopack quirk below)
cd web && npm run build && npm run start               # prod build — required for Playwright/anything you need to trust
cd web && npx playwright test                          # e2e smoke test (signup->login->predict->shortlist)

python -m unittest tests.test_api -v                   # single test module
python -m unittest tests.test_api.TestStudentCRUD -v   # single test class
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
python scripts/load_campus_data.py            # verified campus_area_acres (fail-closed, authoritative single-source only; display-only, NOT a score input)
python scripts/generate_predictions.py        # regenerate predictions (carry-forward model)
python scripts/score_colleges.py              # recompute college quality scores (pillar formula) — MUST run after any college_details/cutoffs change or scores go stale (audit 2026-07-04: this step was missing from the gate and load_db.py silently reverted scores to a broken 1-10-scale flat average on every reload — see college-scoring below)
python -m unittest discover -s tests          # 88 tests: data + engine + API + app cold-load + scoring must all pass
```
- Schema for `predictions_2026` lives ONLY in `constants.ensure_predictions_table` —
  never inline a second `CREATE TABLE` for it (that duplication caused the canonical_code bug).
- `CATEGORY_FALLBACKS`, `YEAR_WEIGHTS`, `canonical_branch_key`, `canonical_college_key` live ONLY in `constants.py`.
- **College quality score is a fixed-weight pillar blend, NOT a flat average** (audit
  2026-07-04): `setup_college_profiles.pillar_score()` is the ONLY place the formula is
  implemented — selectivity (from real cutoff demand, 30%) + academic/placement outcomes
  (45%) + infrastructure (25%), each pillar backfilled by proxy/neutral default when a
  college has zero real subsets there, so data completeness never changes the number.
  Never reimplement this inline (a duplicate `AVG(score)` formula in `load_db.py` silently
  reverted every score to an unscaled 1-10 value on each reload — root cause of colleges
  like COEP/PICT/GCOE Aurangabad showing single-digit "scores"). College identity for
  pairing (4-digit/5-digit codes, codes that survived a name/district rename) is
  `constants.canonical_college_key()` — NEVER group colleges by exact `college_name`
  match again (name text drifts year to year even for the same physical college).
- **Academic pillar = best-credential model, not a flat average** (audit 2026-07-05):
  a flat mean let a data-poor college's lone `year_estd=10` beat a data-rich college's
  real NAAC A/NIRF (PICT > VJTI), and averaged a secondary flag (autonomous=8) down against
  a top grade (COEP's A++=10). Fixes in `setup_college_profiles._academic_pillar`:
  (a) `year_estd`/`affiliation` REMOVED from the academic pillar (age/university aren't
  quality — like campus was removed from infra); (b) accreditation = MAX(naac, nirf) and is a
  FLOOR (a lower positive flag can only RAISE academic above the grade, never lower it);
  (c) no-academic-data → DISCOUNTED selectivity proxy (`selectivity − 2`), so real credentials
  outrank a college we merely lack data for; (d) infra no-data neutral raised 5.0→6.0
  (`NEUTRAL_INFRA_DEFAULT`) since facilities are recorded only when present + near-universal,
  so documentation alone stopped inflating. NAAC/NIRF mappings recalibrated up (NAAC A=9 not 7;
  being NIRF-ranked is elite). Verified ordering: COEP 90 · ICT 90 > VJTI/PICT/SPIT 85.5.
  NAAC data errors are fixed in `apply_data_corrections.CORRECTIONS` from AUTHORITATIVE sources
  only (Walchand A+/C conflict → verified A; ICT missing → A++/NIRF 41) — never guessed.
- **Campus size is displayed, NOT scored** (audit 2026-07-05): `campus_area_acres`
  shows on the profile (Quick Facts + Facilities) but is deliberately EXCLUDED from
  `INFRASTRUCTURE_SUBSETS` in `pillar_score`. Campus AREA is a biased quality proxy —
  it punishes elite compact urban colleges (VJTI/ICT 16ac→4/10, VIT Pune 7ac→2/10) and,
  since those flagships have no other infra subset, feeding it in would drop their infra
  pillar from the neutral 5.0 backfill and LOWER a good college's score simply for having
  real data — the exact completeness-violation the pillar model exists to prevent. Load
  campus data ONLY from an authoritative single-valued source (`load_campus_data.py`);
  aggregator sites disagree (VJTI showed 16/16.5/17 across three) so they are rejected,
  not averaged. Colleges without a clean source stay NULL → shown as "N/A", never guessed.
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
- **Reserved-pool eligibility** (`engine_adapter._eligible_pools`): TFWS/Defence/Orphan/PwD/EWS
  are surfaced as EXTRA seats only from EXPLICIT student flags (`student_profiles.*_eligible`),
  never inferred. EWS is added ONLY when `ews_eligible` is set AND the base category is Open
  (`GOPEN`/`LOPEN`) — a reserved-category student (SC/ST/OBC/SEBC/VJ/NT) is not EWS-eligible;
  it used to auto-add from a low `family_income_bracket`, which surfaced a phantom "EWS pool"
  on students who never chose it (audit 2026-07-05 — do NOT reintroduce income-based EWS).
- **Pool seats are DISTINCT selectable entries, NOT deduped** (audit 2026-07-05): a TFWS seat
  (its own ~6-seat quota) is a different seat from the general seat, so `_merge_pool` appends
  pool rows without collapsing them into the primary row. Identity is `entry_key` =
  `canonical_code` + `::` + seat_pool (plain `canonical_code` for general) — the frontend keys,
  selection, and shortlist de-dup on `entry_key`, never `canonical_code` alone, so a college's
  general and TFWS entries stay separate. Engine rows also carry `branch_code`, `general_intake`,
  `tfws_intake`. Predictions run for CAP rounds 1–4 (`round_num` le=4, not le=3).
- Design rationale: [docs/phase4_design.md](docs/phase4_design.md).

## Known Data Quirks
- **College code format change (2023→2024)**: CET Cell changed from 4-digit (e.g. `3012`) to 5-digit (e.g. `03012`) college codes in 2024. The same physical college appears under different codes (and branch codes) across years. `predict.py` handles this by joining on college_name + branch_name, not branch_code.
- **AI quota rows**: Each AI row in `cutoffs` is one individual student allotment, not a per-branch cutoff. AI cutoff = MIN(percentile) per branch/year/round.
- **Category code spaces**: Parser can produce garbled category codes with spaces (`AI MI`, `AI AI AI...`) for edge-case PDF rows. `load_db.py` now rejects these before insert.
- **Impossible percentiles in official PDFs**: CET Cell's own PDFs contain rows whose printed percentile is impossible for the printed merit number (65 TFWS rows printed `(0.0000000)` against merits like 1102 — verified against source). `constants.find_impossible_percentile_keys` (within-year monotonicity test) gates these at load time and `apply_data_corrections.py` quarantines them from a live DB. NOTE: naive cohort-size bounds do NOT work — 2023's merit-list bottom (~143k) legitimately closes at 0.0x percentile.
- **Dead codes**: canonical branch keys last seen in 2023 cannot be chosen in current CAP (2024 re-numbering). `generate_predictions.py` skips them (`MIN_LATEST_DATA_YEAR`).
- **Seat intake data (audit 2026-07-05)**: real per-branch sanctioned intake comes from a
  DIFFERENT PDF than the cutoff PDFs — CET Cell's "CAPR-I" Provisional Allotment List
  (`https://fe2025.mahacet.org/CAP-I/CAPR-I_{college_code}.pdf`, 2025 Round 1, 368 colleges).
  Each branch has separate course-code sub-entries for general, EWS, and TFWS
  ("...T" suffix) pools, plus sometimes regional/language quota sub-pools ("K"=Konkan,
  "L"=Regional Language) that are ADDITIONAL seats within the general pool, not
  alternates — `parse_seat_intake.py` sums same-bucket sub-entries per canonical branch
  rather than treating differing values as a conflict (a real bug during development:
  folding EWS into "general" produced false conflicts on ~380 branches). `general_intake`
  and `tfws_intake` in `branch_intake` are the two numbers the UI shows as "X + Y" — EWS
  is parsed but not currently surfaced. Intake is a fixed institutional capacity, sourced
  once from Round 1; it is not re-fetched per round.

## API — `api/` (FastAPI)
- `api/main.py` wires routers under `/api/*` (`auth`, `lookups`, `students`, `predictions`, `colleges`, `branches`, `me` for counselor shortlist) and mounts `/static/images` for locally-downloaded college photos. CORS is locked to `http://localhost:3000`.
- `api/db.py` opens the **same** `db/edupath.db` the engine/scripts use (no separate API database) and owns only the API-specific tables it creates itself (`student_profiles`, `student_shortlists`, `college_descriptions`, `counselors`, `counselor_shortlists`) — idempotent `CREATE TABLE IF NOT EXISTS` + guarded `ALTER TABLE` migrations in `init_tables()`, run on every app startup via the `lifespan` hook. It also adds `app/` to `sys.path` so routes can import `engine_adapter` directly instead of duplicating engine logic.
- Auth (`api/auth_utils.py`): bcrypt-hashed passwords, JWT (HS256) with `JWT_SECRET` from `.env` resolved **at call time, not import time** (so import order can't freeze an empty secret) and fails loudly rather than signing with `""`. `get_current_counselor_id` is the FastAPI dependency every counselor-scoped route uses.
- `web/lib/api.ts` is the **only** place the frontend talks to the API — no raw `fetch()` elsewhere. `request()` handles unreachable-backend and non-2xx errors; `authRequest()` layers on the bearer token from `localStorage`.

## Frontend — `web/` (Next.js 16.2.9 + FastAPI `api/`)
- Counsellor-facing web app, App Router, client components. Backend: `uvicorn api.main:app` on port 8000 (repo root). Frontend: `npm run build && npm run start` (port 3000) — see the Next.js quirk warning below for why NOT `npm run dev` for anything you need to trust.
- **This Next.js version has undocumented breaking changes from training-data expectations** (`web/AGENTS.md`) — read `node_modules/next/dist/docs/` before assuming familiar API behavior.
  - **Confirmed quirk (2026-07-05, `web/app/compare/page.tsx`)**: `router.push()`/`router.replace()` to the SAME pathname with only the search-query string changed silently no-ops — no error, the address bar and `useSearchParams()` never update. Don't drive UI state off `useSearchParams()` reactivity for same-page query changes; use local `useState` seeded once at mount, and sync the address bar (if needed) via the raw `window.history.replaceState()` API instead of the router.
- Auth: JWT in both localStorage (`edupath_token`) and a same-name cookie (for `web/middleware.ts` route gating).
- Key pages/flows:
  - **Discover** (`app/page.tsx`) — college list with filters (`DiscoveryFilters.tsx`: Score range, Cutoff percentile range), working Sort dropdown (Score / Cutoff percentile), `CompareButton`/`CompareTray` entry points.
  - **College profile** (`app/colleges/[code]/page.tsx`) — identity, copyable institute/paired codes, accreditation, fees by category, score breakdown, campus size (Quick Facts, display-only), branches table with Code column, cutoff trends 2023→2026.
  - **Branch forecast** (`app/branches/[canonicalCode]/page.tsx`) — CAP Round R1–R4 selector, 2026 predicted + 2025 actual close + seat intake, collapsible category tree (families Open/OBC/SC/ST/EWS + "More categories"; grouping logic in `web/lib/categories.ts::parseCategory`).
  - **Student flow** (`students/[id]/results`, `students/[id]/shortlist`) — R1–R4 round selector on results, floating shortlist bar, TFWS/reserved-pool seats shown as distinct entries (keyed by `entry_key`, never `canonical_code` alone), shortlist page has framer-motion drag-to-rank (`Reorder`), sort dropdown, print-to-PDF via `window.print()`.
  - **Bookmarks** (`app/my-shortlist/page.tsx`, nav item, was "My Shortlist"/heart icon — now "Bookmarks" with a Bookmark icon).
  - **College Compare** (`app/compare/page.tsx`, `?codes=a,b,c`, 2–4 colleges, 91mobiles-style) — `web/lib/useCompare.ts` (localStorage `edupath_compare_v1`, min 2/max 4, independent of counsellor account), `CompareButton` (`chip`/`full` variants), `CompareTray` (global floating tray in `app/providers.tsx`, hidden on `/login`/`/signup`/`/compare`). Sticky top card row + 7 collapsible comparison sections + "Highlight differences" toggle.
    - **Grid alignment rule**: the sticky card row's `gridTemplateColumns` (including gap=0) must stay pixel-identical to every data row's grid, or columns drift — visual spacing must come from padding inside cells, never a grid `gap`.
    - **Sticky/overflow rule**: never wrap the sticky card row in an `overflow-x-auto` container — per the CSS Overflow spec, a non-`visible` `overflow-x` forces `overflow-y` to compute as `auto` too (cannot be overridden by an explicit `overflow-y-visible` class), which makes the wrapper an unintended scroll container and breaks `position: sticky`'s containing block. Let rare horizontal overflow fall through to the page.
- **Edit-not-saving class of bug**: React Query caches (e.g. predictions, 5-min staleTime) must be explicitly `queryClient.invalidateQueries(...)` after any mutation (student edit, shortlist save) — nothing invalidates them automatically.
- Playwright (`web/playwright.config.ts`): `webServer.command` MUST be `"npm run build && npm run start"`, never `"npm run dev"` — Turbopack dev mode spawns 40+ orphaned `node .next/dev/build/*.js` workers on this machine and never converges (kill via `Get-CimInstance Win32_Process -Filter "Name='node.exe'"` + `Stop-Process` if they pile up).

## Data Collection Status (per physical college, 408 total canonical; measured 2026-07-05)
- campus_area_acres 21/408 (5%, authoritative-source-only via `load_campus_data.py` — see scoring notes above)
- naac_grade 129/408 (31%) · nirf_rank 14/408 (3%)
- placement_pct 8/408 (1%) · avg_package_lpa 2/408 · top_recruiters 0/408 — **biggest gap, highest priority to fill next**
- fees 28/408 (6%, FRA per-category) · year_established 256/408 (62%) · branch_intake 368 colleges (good)
- Priority order for future collection: placements → NAAC for the missing 69% → infra/campus for more colleges. Always use the fail-closed, authoritative-single-source discipline above (no aggregator averaging, no guessing — NULL stays NULL, shown as "N/A").

## Naming
- Files/folders: snake_case
- DB tables/columns: snake_case
- Python: PEP 8

## Verification Checklist
1. `flagged_reviews` table is empty or all items reviewed
2. Random spot-check: 50 rows vs source PDF by eye
3. Cross-check known colleges (COEP, VJTI, PICT) against published cutoffs
4. Row counts per college-branch match expected category count

## Working in this environment
- A Python script launched via a background shell writes NOTHING to its output file until it exits (stdout fully buffers when not a TTY) — an empty output file after minutes of runtime is normal, not a hang. Verify liveness via process CPU time, not output content. Use `python -u` when live progress visibility actually matters.
