# Full-Project Audit — 2026-07-02 — Running Notes

One entry per finding/lesson. Summary line first, detail under it.

## Setup
- **Baseline**: 68 tests pass before any change. Working tree had uncommitted Phase 5b WIP (auth, dashboard, discovery) — committed as baseline so audit changes are isolated.

## Findings log

### Section 1 — Data foundation (before 6/10, after 9/10)
- **FIXED: 65 TFWS cutoff rows with impossible percentiles (source-PDF glitch).** CET Cell's own PDFs print e.g. "(0.0000000)" against merit 1102 (verified page 266 of 2024_CAP1_MH.pdf, ICT Pharma-Chem TFWS). MIN() aggregation made 0.0 the closing cutoff → ICT TFWS (real close ~99.9) predicted at 0.0 → SAFE for anyone. Detector = within-year monotonicity vs merit_no (`constants.find_impossible_percentile_keys`); naive cohort-size bounds DON'T work because 2023's list bottom (merit ~143k, pct 0.0x) is legitimate. Gate added to load_db.py (fail-closed → flagged_reviews) + quarantine in apply_data_corrections.py (heals live DB). 65 rows quarantined, predictions regenerated.
- **FIXED: 3 colleges (279 prediction rows) invisible to the preference engine** — present in `colleges`/`predictions_2026` but missing from `college_details`, and the engine INNER JOINs college_details. Added `ensure_details_rows()` to populate_university_map.py (stub row + district from city). All 3 now resolve a university (MU/RTMNU).
- **Solid**: 0 percentile bounds violations, 0 referential-integrity orphans, 0 garbled categories, 0 exact duplicate keys (per seat_type), university_code coverage 716/716, all districts resolvable, merit_no all positive, flagged_reviews mechanism works.
- Note: the same category code can legitimately appear under two seat_type headings (H-seat allotted to other-univ candidate); MIN() across them is the correct closing for that pool.
- Note: 2023 percentile↔merit mapping is NOT a single cohort curve (implied N varies 158k–247k) — never build a gate on absolute cohort size.
- Remaining for 10/10: 180 college_details rows have NULL district (display-only impact); the lone pct=100.0 row (2024 LOPENO merit 13) is plausible and left in.

### Section 2 — Parsing & loading (before 6/10, after 8.5/10)
- **VERIFIED SOLID: chunk-boundary safety.** Feared the 150-page chunking loses rows when a college section spans a boundary; tested splits at 5 arbitrary pages — 0 records lost (every PDF page is self-contained, headers reprinted). No fix needed.
- **VERIFIED SOLID: parse fidelity.** 3 random 2025 R1 rows (merit + percentile) match 2025_CAP1_MH.pdf exactly; ICT glitch row matched source page 266 char-for-char.
- **FIXED: 12 physical colleges (17 code rows) had a scraped district resolving the WRONG home university** — e.g. Cummins College (Karvenagar, Pune) stored NAGPUR→RTMNU; Sipna Amravati stored SINDHUDURG→MU. Home/Other seat eligibility was flipped for every student at those colleges. New `fix_districts_from_official_name` in apply_data_corrections.py: the official CET name's LAST location token is authoritative; only acts when universities disagree. Idempotent (2nd run: 0).
- **OPEN ITEM:** ~15 colleges have city/district conflicts with NO location in the official name (03277, 03445, 03546, 02641, 02666, 06315, 06318, 06326, 06444, 06185, 06268, 02634, 02770, 02777, 03723) — need manual verification; district precedence stands meanwhile.
- SKIPPED (low-risk): full token-count reconciliation of every PDF vs DB (hours of CPU; boundary tests + spot checks + Section 1 cross-field gate cover the realistic failure modes). Category whitelist gate skipped: all 95 live category codes already match the legend pattern; a hard whitelist risks rejecting rare real codes.

### Section 3 — Prediction engine (before 4/10, after 8.5/10)
- **FIXED (biggest finding of the audit): linear-trend extrapolation is 44% WORSE than carry-forward.** Backtest on 27,772 groups (fit 2023+2024 → score vs actual 2025): linear MAE 13.5/bias +4.7 vs carry-forward MAE 8.3/bias −0.5. Carry wins in EVERY stratum (elite/mid/low cutoffs, stable/volatile) and at every damping level d>0 — year-to-year cutoff movement is noise-dominated, trend-following doubles the noise. `generate_predictions.py` now predicts the latest year's closing; LS slope kept as display-only trend metadata. Permanent harness: `scripts/backtest_predictions.py` (warns if a trend model ever starts winning when new data lands).
- **FIXED: confidence ignored volatility.** Carry error is 3.5 MAE at spread<2 but 11.4–14.2 at spread>10. Predictions from histories with spread >10 pts are now `low` confidence (never SAFE). High-confidence count honestly dropped 25.7k→13.3k.
- **FIXED: probability sigmoid was overconfident.** Calibration vs actual 2025 outcomes (~350k samples): old k=0.4/clamp-0.98 claimed 90–100% for seats that materialised 80% of the time. Now k=0.25/clamp-0.93: top band (80–90%) matches its observed 80.0% rate; tool never claims >93%/<7%.
- Lesson: never trust a hand-picked model parameter without scoring it on held-out real outcomes — every hand-picked value here (d=1 trend, k=0.4, clamp 0.98, years-only confidence) was measurably wrong.
- Remaining for 10/10: symmetric sigmoid can't express asymmetric tail risk; per-branch volatility could set per-branch probability width; 3 data years is a hard ceiling. Bands (+3/−1/−4) were locked in phase4_design.md — with carry MAE ~5.5 on non-volatile branches, SAFE≥+3 is borderline-generous but the low-confidence gate covers the worst cases; flagged as a recommendation, not changed.

### Section 4 — Preference engine / seat eligibility / round strategy (before 6.5/10, after 8/10)
- **FIXED: 14,301 predictions (10%) were for DEAD codes** — canonical keys last seen in 2023 (CET's 4→5-digit re-numbering). Students were being shown 2026 options that cannot be chosen in the 2026 CAP; re-coded colleges already have live predictions under new codes. generate_predictions now skips groups with max_year < 2024 (`MIN_LATEST_DATA_YEAR`).
- **FIXED: band counts computed after top_per_band truncation** — CLI said "SAFE: 5" when 200 existed. Counts now reflect all eligible options.
- **VERIFIED SOLID:** H/O/S seat resolution (out-of-state student granted 0 Home seats, live-checked), band honesty at the top (99.8 Pune student sees COEP CSE as PROBABLE at −0.10 margin, not oversold), round strategy drops now = observed 2025 R1→R3 drops (~1.3 pts, credible), budget filter never silently drops unknown-fee colleges, fee calculator fail-explicit (tests).
- **RECOMMENDATION (not executed — changes band semantics everywhere):** margin bands are level-blind. At elite branches (close ≥97, carry MAE 0.42) SAFE≥+3 is mathematically unreachable (100-cap), so even a 99.99 student never sees VJTI/COEP as SAFE; at low branches (MAE 13) +3 is too lax. Bands should scale with tier volatility. Locked in phase4_design.md, needs owner sign-off.

### Section 5 — College data layer (before 6/10, after 8/10)
- **FIXED: cutoff trend line mixed rounds** — history columns were MIN across ALL rounds while the 2026 column is a round-1 prediction, so every profile showed a spurious 2025→2026 "rise" (a later-round close is always lower). History now round-1 like the prediction. COEP CSE now reads 99.92 / 99.97 / 99.90 / 99.90.
- **FIXED: renamed branches split into two trend rows** (COEP CSE 2023 name vs 2024+). BRANCH_NAME_ALIASES now applied in `_cutoff_trends`.
- **FIXED: 115 college names had different scores on the 4-digit vs 5-digit code** (gaps up to 25 pts — score depended on which code a caller referenced). `sync_paired_code_scores` in setup_college_profiles.py scores each name over the union of subset scores; 315 name groups unified, 0 inconsistencies remain.
- **Solid:** subset scores all within 1–10; fees 11k–156k plausible; no placement_pct/year_established outliers; profile API fail-soft with paired-code fallback.
- **OPEN ITEM (data, not code):** FRA fee data covers only 28/379 colleges (fail-explicit elsewhere — correct behavior, but budget filtering is blind for 93% of colleges). Placement/infra fields similarly sparse. Needs a data-collection effort, not code.

### Section 6 — API layer (before 6/10, after 8.5/10)
- **FIXED: JWT secret read at import time with "" fallback.** If .env were missing (or a module imported auth_utils before api.db's dotenv loader ran) every token would be signed AND verified with the empty string — fully forgeable auth. Secret now resolved lazily per call and hard-fails when unset.
- **FIXED: branch deep-dive lost 2023 history for EVERY branch** — history filtered by predictions_2026.branch_code (recent 10-digit codes only), but 2023 rows use un-padded 9-digit codes. Now resolves all codes via canonical_branch_key (PICT & COEP verified 2023-2025).
- **FIXED: signup race** on UNIQUE(email) returned 500; now 409.
- **Solid:** ownership enforced on every student/shortlist route (counsellor_id from JWT, never from client), Pydantic bounds on percentile/round, parameterised SQL throughout (no injection paths found), asyncio.to_thread keeps SQLite off the event loop, search pagination capped at 200.
- Notes for deployment (not v1 issues): no login rate-limiting/lockout; description generate/edit endpoints are unauthenticated (local single-tenant OK); CORS pinned to localhost:3000.

### Section 7 — Frontend (before 7/10, after 8.5/10)
- **FIXED: false data claim** — branch page footer said forecasts are "based on 11 years of CAP data"; it's 3 (2023–2025). Now says 2023–2025.
- **FIXED: empty-state band descriptions misstated the thresholds** (PROBABLE claimed "±3 points"; actual band is −1..+3 margin).
- **VERIFIED SOLID:** `npm run build` clean (TypeScript strict, 13 routes); auth plumbing correct (cookie mirrors localStorage, /me validates token, middleware gates pages while API re-verifies signature); optimistic shortlist updates roll back on API failure; honest-uncertainty UX everywhere (confidence badges, fallback seat-data warnings, unresolved-district banner, Fee N/A never ₹0); zod client validation mirrors server bounds.
- SKIPPED (low risk, one line): full accessibility/contrast audit and cross-browser pass — internal B2B tool, Radix primitives handle most of it.
- Remaining for 10/10: zero automated frontend tests (no component/E2E coverage); PredictionResult TS type omits counts.location_hidden (display-only).

### Section 8 — Test suite & QA (before 7/10, after 8.5/10)
- Suite grew 68 → 71 during the audit (impossible-percentile gate, college_details coverage, carry-forward semantics ×2, volatility flag).
- Full verification gate re-run end-to-end: idempotent, green. `backtest_predictions.py` prints an explicit WARNING if a trend model ever beats carry-forward on new data.
- CLAUDE.md updated: gate steps, 71-test count, carry-forward model rule (never reintroduce extrapolation without a winning backtest), impossible-percentile + dead-code quirks.
- Remaining for 10/10: no frontend tests; backtest is a script, not CI; "50 rows by eye vs source PDF" checklist item still manual (3 rows automated this audit).
