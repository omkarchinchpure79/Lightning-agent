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

### 3.1 Data pipeline (new scripts, FE pipeline untouched) — DONE, verified 2026-07-06
- `scripts/download_dse_pdfs.py` — downloads + header-verifies all 7 PDFs.
- `scripts/parse_dse_cutoffs.py` — column-aligned parser (values are assigned to
  categories by x-coordinate, never reading order — a stage row can cover any
  subset of categories). 71,034 rows parsed, 0 flagged after three real-world
  fixes: (1) a course name can wrap onto its own line BEFORE the Choice Code
  line — only recognised via 1-line lookahead (a genuine single-category header
  is always followed by a merit number, a wrapped title by a Choice Code line;
  465/7679 sampled blocks are genuinely single-category, so this can't be
  guessed without the lookahead); (2) choice codes can carry a trailing
  seat-sub-type letter (F/U/L, e.g. `303524550F` at a women's-university
  college); (3) stage labels are not a closed set (`Stage-I`, `Stage-VII`,
  `Stage-MI`, `I-Non PWD / DEF` all observed) — stored as free-text `stage`,
  never matched against a hardcoded roman-numeral list.
- `scripts/load_dse_db.py` → `dse_cutoffs` table (mirror of `cutoffs` minus seat-type,
  `merit_pct` = diploma percentage). DSE data NEVER mixes into the `cutoffs` table.
  **Does NOT apply FE's impossible-percentile monotonicity gate** — verified
  (2026-07-06) that DSE `merit_no` is a PER-BRANCH waitlist rank, not one
  statewide list per category like FE's; running the FE gate flagged 17
  legitimate rows as false positives because it compared unrelated branches'
  independent rank sequences. See the long comment in `load_dse_db.py`.
- `dse_predictions` via the same carry-forward model (`predicted = latest year's
  close`) and the same empirically-calibrated interval method
  (`constants.interval_offsets_from_groups`, factored out of
  `compute_interval_offsets` so both planes share one implementation).
  33,089 predictions generated (6,559 high / 8,085 medium / 18,445 low confidence).
- Category canonicalisation: `constants.py` has `DSE_CATEGORY_LEGEND` (34 tokens,
  frozen from a full-corpus census) and `DSE_CATEGORY_MAP` (FE base category →
  DSE cutoff category, NTA/NTB/NTC/NTD ↔ VJ/NT1/NT2/NT3). Confirmed via census:
  DSE prints NO TFWS at all; PwD-Open and Defence-Open DO exist in DSE (`PWD-O`,
  `DEF-O`) alongside the per-reservation `PWDR-*`/`DEFR-*` variants.

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

## 4.5 Frontend integration — DONE, verified 2026-07-06

Per-student `admission_type` toggle on `StudentForm` (First year / Direct Second Year):
DSE mode swaps percentile→diploma %, hides TFWS/PwD/Defence/Orphan/EWS toggles (DSE
selects those as plain categories instead) and the Home district card (no H/O/S layer
in DSE), and filters the category dropdown to `dse_supported` codes only. Results page
labels the header correctly ("% diploma" vs "%ile"), shows a "Direct Second Year
(diploma merit)" tag, and offers only CAP rounds I–II. Students list/shortlist/edit
pages all display the right unit label per student.

**Real bug found and fixed during click-through testing** (not a tooling artifact):
switching `admission_type` unmounts the other mode's merit-mark input
(`percentile`/`diploma_pct`), but react-hook-form does not clear an unmounted field's
value by default. An untouched number input resolves to `NaN` via `valueAsNumber`,
which fails `z.number()` validation — and because each field's error message is only
rendered inside its own conditional branch, a stale error on the now-hidden field was
completely invisible: "Create & run predictions" did nothing, no error text, no network
request. Fixed with a `useEffect` that explicitly `setValue`s the inactive field to
`null` on every admission-type toggle (chosen over `useForm({ shouldUnregister: true })`,
which was tried first but has a wider blast radius — it also resets other
conditionally-rendered Controllers, like the category/home-district selects, on
unrelated re-renders). Verified end-to-end: DSE student created, results page renders
all three bands from `dse_predictions`, shortlist add/list works, edit page reloads
correctly into DSE mode.

## 4.6 College profile DSE tab + predict.py CLI parity — DONE, verified 2026-07-06

Closed the last two gaps for full symmetry between the FE and DSE planes across every
surface (not just the primary web workflow):

- **College profile page** (`app/colleges/[code]/page.tsx`): a "Direct Second Year
  (diploma) cutoffs" section, sourced from `college_card_api.get_college_profile()`'s new
  `dse_cutoff_trends` field (mirrors `_cutoff_trends` exactly: GOPEN category, round 1
  only -- same reasoning as FE, a later round's close is always lower and would make the
  trend line lie -- across all paired college codes). Renders only when the college has
  DSE data (`.length > 0`); silently absent otherwise, since not offering DSE is the
  common case, not a fault. Verified in-browser both ways: GCOE Amravati (1002) shows 7
  branches matching the parser spot-check (CSE 93.32/93.21/94.00, matches
  `tests/test_dse.py`'s known value); Vidya Prasarak Mandal's College of Engineering,
  Thane (03257, confirmed zero DSE rows across paired codes) shows no DSE section at all
  while its FE branches table still renders normally.
- **`predict.py` CLI**: added `--admission-type {fe,dse}` (default `fe`). DSE path reads
  `dse_cutoffs`/`dse_predictions` directly (no `branches` join needed -- unlike FE,
  `dse_cutoffs` already carries college_code/college_name/course_name per row), validates
  `--category` against `DSE_CATEGORY_LEGEND`, and validates `--round` against
  `DSE_VALID_ROUNDS` (1-2, not 1-4). City filtering still works via a `LEFT JOIN`
  against `colleges` (DSE college_code values are the same institute codes FE uses).
  Reuses `compute_probability()` (the k=0.25 sigmoid) unchanged -- confirmed during this
  work that the web app's `preference_engine`/`dse_engine` never compute a numeric
  probability at all (only SAFE/PROBABLE/REACH bands from margin), so the "recalibrate
  the sigmoid for DSE" item in section 3.2 only ever applied to this standalone CLI tool,
  which wasn't wired to admission_type before now. The CLI's probability is explicitly
  documented as directional/uncalibrated for DSE (not backtested against real DSE
  outcomes the way FE's k/clamp values were) rather than presented as equally precise.

## 5. Open items
- 2024-25/2025-26 Round III: never published publicly; predictions for rounds beyond II
  in those seasons must say "no data", not extrapolate.
- DSE seat-intake (lateral quota per branch): no official per-branch PDF found yet;
  display "N/A" until an authoritative source is found.
- The ~25 ten-digit choice codes in the 2025 PDF: verified non-issue (2026-07-06) -- the
  parser derives `college_code` from the college header line, not the choice code, and
  validates every choice code starts with its college's code (0 flags across all 71,034
  rows), so these are legitimate longer codes, not a parsing bug.
- DSE probability sigmoid (predict.py CLI only): reuses FE's k=0.25/93% clamp as-is,
  not independently calibrated against DSE outcomes. Low priority -- the CLI is a
  secondary surface; the primary web workflow doesn't expose a numeric probability at
  all for either plane.
