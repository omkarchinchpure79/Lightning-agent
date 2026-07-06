# Session 2 — Direct Second Year Engineering (DSE) Feature Design

**Branch:** `direct-second-year-admission` · **Status:** data acquired + verified, design approved-pending, implementation not started.
**Product decision (2026-07-06):** DSE is selected **per student** — the student profile gets an
"admission type" (First Year / Direct Second Year). No app-wide mode switch, no separate /dse area.

## 1. What DSE is (verified 2026-07-06)

Direct Second Year Engineering = lateral entry into the 2nd year of BE/BTech for **diploma
holders** (and eligible B.Sc/B.Voc graduates), run by the same Maharashtra CET Cell through a
CAP process that mirrors the first-year one (registration → merit list → option form → CAP
rounds → allotment → cutoff lists per round).

Key structural differences from first-year (FE) admission, all confirmed against the official
cutoff PDFs (not just secondary sources):

| Dimension | First Year (existing system) | DSE (this feature) |
|---|---|---|
| Merit basis | MHT-CET **percentile** (0–100, rank-derived) | **Diploma aggregate percentage** (marks %). Same 0–100 range, totally different distribution — never comparable across the two systems. |
| Cutoff value printed | merit no + percentile | merit no + percentage, e.g. `1282 (92.74%)` |
| Seat pool | Sanctioned first-year intake | Lateral-entry seats ≈ 10% of intake + vacancies; **no seat-intake PDF equivalent found** — intake display must fail-explicit ("N/A") |
| Seat types | H / O / S / AI per category (GOPENS/GOPENH/…) | **No H/O/S suffixes at all** — the entire Home/Other-university eligibility machinery is bypassed for DSE |
| Categories | GOPENS, GSCS, … GVJS, GNT1S… | `G`/`L` × OPEN, SC, ST, OBC, SEBC, **NTA/NTB/NTC/NTD** + EWS, MI, PWD/PWDR, DEF/DEFR. Mapping to FE families: GNTA≈GVJ (VJ/NT-A), GNTB≈GNT1, GNTC≈GNT2, GNTD≈GNT3 |
| TFWS | Own quota, distinct entries | **Zero TFWS mentions in the entire 2025 R1 PDF** — no TFWS pool in DSE |
| Rounds published | 3–4 per year | 2023-24: rounds I–III; 2024-25: I–II; 2025-26: I–II (complete public corpus) |
| College codes | 4-digit (2023) → 5-digit (2024+) | Predominantly 4-digit even in 2025 (2,020 of 2,045 choice codes are 9-digit = 4-digit college + 5); a small tail is 10-digit |
| PDF format | One PDF per college-type × round; 2024+ behind base64 `ViewPublicDocument.aspx` | **One consolidated statewide PDF per round**, direct static URL — much simpler than FE |
| Stages | I, II, VII… | I and II observed |
| Scale (2025 R1) | ~245k cutoff rows total (all years) | 596 college entries · 2,045 college×branch choice codes per round |

Same as FE: page layout of the cutoff PDF (college line → `Choice Code : NNNNNNNNN Course
Name : X` → category header row → merit row → `(percent)` row → Stage), the college identity
space (same institute codes as FE — GCOE Amravati is 1002 in both), the CAP-round concept, and
the reservation-category families.

## 2. Data acquired (all fail-closed header-verified)

`data/raw/pdfs/dse/dse_cutoff_{year}_round{n}.pdf` — 7 files, ~13.6 MB, re-downloadable via
`python scripts/download_dse_pdfs.py`:

| Season | R1 | R2 | R3 |
|---|---|---|---|
| AY 2023-24 | 592 pp | 848 pp | 680 pp |
| AY 2024-25 | 632 pp | 896 pp | — not published |
| AY 2025-26 | 682 pp | 983 pp | — not published |

**Provenance trap discovered:** each season's portal (`dseNNNN.mahacet.org.in`) links the
*previous* season's cutoffs as "CAP Round - I/II/III" reference — the dse2024 portal's links
are the AY 2023-24 files. Additionally the dse2024 staticFiles directory currently 403s
server-side. Consequences baked into `download_dse_pdfs.py`:
- Never trust URL/filename year — verify the `for AY YYYY-YY` + `CAP Round N` header inside
  every PDF, reject on mismatch.
- 2023-24 files come from Internet Archive snapshots of the official URLs; 2024-25 files come
  from the dse2025 portal's official re-publication.

## 3. Architecture: same machine, second data plane

Everything the user called "the same" genuinely is the same and is reused untouched:
college identity (`colleges`, `college_details`, scores, photos, descriptions, compare,
bookmarks), counsellor accounts, students CRUD, shortlists, the band model
(SAFE/PROBABLE/REACH on margin), carry-forward prediction, the UI shell.

What is new / different:

### 3.1 Data pipeline (new scripts, FE pipeline untouched)
- `scripts/download_dse_pdfs.py` — DONE (verified sources above).
- `scripts/parse_dse_cutoffs.py` — parse the 7 PDFs → same validation gates as FE
  (`category_count == pair_count`, 0≤value≤100, known category legend — the **DSE** legend,
  known institute code) → flagged rows go to `flagged_reviews` with a `source='dse'` marker.
- `scripts/load_dse_db.py` → new table `dse_cutoffs` (mirror of `cutoffs` minus seat-type,
  plus `merit_marks_pct` semantics). DSE data NEVER mixes into the `cutoffs` table —
  percentile and percentage must be un-joinable by construction.
- `dse_predictions_2026` via the same carry-forward model (`predicted = latest year's close`),
  schema owned by one function in `constants.py` (same single-source rule as
  `ensure_predictions_table`). Backtest before ever doing anything fancier — same rule as FE.
- Category canonicalisation: extend `constants.py` with `DSE_CATEGORY_LEGEND` and the
  NTA/NTB/NTC/NTD ↔ VJ/NT1/NT2/NT3 family mapping so the frontend's category-family tree
  (`web/lib/categories.ts`) can group DSE categories with the same UX.

### 3.2 Engine
- `preference_engine` gets a DSE path with the H/O/S seat-eligibility resolution **disabled**
  (no seat types in DSE) and no TFWS/EWS-pool merging (no TFWS; EWS is a plain category
  column in DSE, not a separate pool). Bands/margins/rounds logic identical, but margin is
  computed on diploma % vs predicted closing %.
- Probability sigmoid must be **recalibrated on DSE data** (k=0.25 was fit on percentile
  spreads; diploma-percentage spreads differ). Calibrate against actual 2025-26 outcomes the
  same way predict.py was.

### 3.3 API + DB
- `student_profiles.admission_type` — `'fe'` (default, backfills existing rows) | `'dse'`;
  plus `diploma_pct` (the DSE merit mark). Guarded `ALTER TABLE` in `api/db.py::init_tables`.
- Validation fail-closed: a DSE student requires `diploma_pct`; DSE base categories are
  validated against the DSE legend (NTA–NTD naming), FE students against the FE legend.
- `/api/students/{id}/predictions` routes to the DSE engine path when the student is DSE.
- Branch-forecast + college endpoints grow an optional DSE view (a college profile can show
  a "DSE cutoffs" tab only when that college has DSE data).

### 3.4 Frontend
- Student form: "Admission type" selector at the top (First Year / Direct Second Year).
  Choosing DSE swaps the percentile field for "Diploma aggregate %", hides TFWS toggle,
  shows the DSE category list. Everything downstream (results bands, round selector R1–R2/R3,
  shortlist, print) reuses the existing components — labels must say "percentage", never
  "percentile", for DSE students.
- Where DSE data is absent for a college/branch, the UI says so explicitly (golden rule:
  never blend FE numbers into a DSE view or vice versa).

## 4. Verification plan (the same non-negotiable gate, extended)
- New unit tests: DSE parser (known-college spot checks against the PDF by eye: GCOE
  Amravati Civil 2023 R1 GOPEN = 393 (93.32%) …), legend validation, engine DSE path
  (no H/O/S, no TFWS), API admission-type validation, and a cold-load app test.
- The existing 106 tests must stay green untouched — FE behavior is frozen while this
  branch develops.
- Cross-check twice: every pipeline number spot-checked against the source PDF after
  parsing AND after DB load.

## 5. Open items
- 2024-25/2025-26 Round III: never published publicly; predictions for rounds beyond II
  in those seasons must say "no data", not extrapolate.
- DSE seat-intake (lateral quota per branch): no official per-branch PDF found yet;
  display "N/A" until an authoritative source is found.
- The ~25 ten-digit choice codes in the 2025 PDF need a look during parser development
  (5-digit college codes for a handful of institutes).
