# EduPath UI Rulebook — Functional Requirements

**What this file is:** a page-by-page list of what must exist and how it must behave —
required data, required buttons/actions, required states — extracted from the current
`web/` app. It is NOT a style guide: colors, spacing, fonts, layout, and component choice
are all open to redesign.

**How to use it:** any visual redesign ("Claude design" or otherwise) is free to change how
something looks, but may not remove a rule below, change what data it shows, or break the
behavior it describes, without the product owner explicitly signing off on that specific
rule. If a rule conflicts with a new design direction, flag it — don't silently drop it.

**Golden rule inherited from the data layer** (see root `CLAUDE.md`): if data is missing,
say so explicitly ("Fee N/A", "Not available", "—") — never guess, never show a fabricated
or zero value in place of missing data. Every rule below that mentions a fallback exists
because of this principle.

---

## 1. Global rules (apply on every page)

### 1.1 Navigation bar
Present on every page except Login/Signup:
- Logo, linking to Discover (`/`).
- **Discover** link.
- **Bookmarks** link, with a numeric badge showing the current bookmark count when > 0.
- **Compare** link, with a numeric badge showing the current compare-list count when > 0.
- Omnipresent college quick-search (type-ahead, min 2 characters, navigates straight to
  that college's profile on pick).
- Theme toggle (light/dark).
- **When logged out:** a "Log in" action, visible and reachable from every page.
- **When logged in:** **Students** link and **Dashboard** link both appear (they must
  NOT be reachable/visible when logged out); a counsellor identity indicator (name/initials)
  and a **Log out** action that returns the user to Discover.

### 1.2 Auth gating
- **Dashboard** and **Students** (list, new, edit, results, shortlist) pages require a
  logged-in counsellor. An unauthenticated visit must redirect to **Login**, not show an
  empty/broken page.
- **Login** and **Signup** succeed by logging the user in and returning them to Discover.
- **Login → Signup** and **Signup → Login** links must be present on each auth page.
- **Anonymous-to-account bookmark merge**: if a visitor bookmarked colleges before logging
  in (local, unauthenticated storage) and then logs in, they must be asked whether to save
  those bookmarks to their new account or discard them — never silently merged, never
  silently dropped.

### 1.3 Two distinct saved-list concepts — do not merge them
- **Bookmarks** ("My Shortlist" in code) — a counsellor-level saved-college list, independent
  of any student. Anonymous users get a local (device-only) version; logging in switches to
  an account-backed version reachable from any device.
- **Compare list** — a separate, always-local (never account-synced) pick-list of 2–4
  colleges for side-by-side comparison. Adding a college to Compare must never add it to
  Bookmarks, and vice versa. A global floating "Compare tray" must stay visible across the
  whole app (except on Login, Signup, and the Compare page itself) whenever the compare
  list is non-empty, showing the current picks and a way to jump into the full comparison
  once at least 2 are picked (max 4).
- **Student Shortlist** — a per-student ranked preference list of specific branch/seat-pool
  entries (not just colleges), produced from that student's prediction results. Distinct
  from both of the above; one student's shortlist must never leak into another student's or
  into the counsellor-level Bookmarks.

### 1.4 Identity & code display
- Every college must expose its **official institute code**, shown in a copy-to-clipboard
  control, on its profile. If the same physical college has other paired/historical codes,
  those must also be shown and individually copyable.
- Every branch listing (college profile branches table, branch forecast page, prediction
  result cards/tables, shortlist rows) must show the **official course/branch code** when
  known, in a copyable form; when not known, show an explicit placeholder, never blank.

### 1.5 Missing-data display rules (non-negotiable)
- Fee unavailable → "Fee N/A" (never ₹0, never blank).
- Score/percentile/rank/rating unavailable → "—" or "Not available" (never 0, never guessed).
- A college with zero photos → a placeholder graphic, never a broken-image icon.
- Any profile section with no underlying data (placements, facilities, contact, branches)
  must render an explicit "not available" message for that section rather than an empty box.
- Predicted percentiles must never visually round up to a value the model didn't reach —
  a true value under 100 must never display as "100".
- Predictions carry a confidence level (high/medium/low) and, for CAP Round 4 rows with
  only one year of data, an explanation that this is structural (R4 is new), not a
  low-quality prediction — this distinction must remain visible, not collapsed into a
  generic "low confidence" label.
- A seat-intake figure sourced via fallback logic (not an exact per-branch match) must be
  visually flagged as a fallback, not presented identically to an exact figure.

### 1.6 Category & branch grouping
- MHT-CET category codes (~100 per branch) must never be shown as one flat list. They are
  grouped into families (Open, OBC, SC, ST, EWS, VJ, NT1–3, SEBC, TFWS, Defence, PwD,
  Orphan). Only families with actual data for that branch are shown — none invented.
  Common families (Open, OBC, SC, ST, EWS) are shown by default; the rest sit behind an
  explicit "more categories" expansion. Each family is collapsible to reveal its individual
  Home/Other/State/Ladies variant rows.
- A reserved-pool seat (TFWS, EWS, Defence, Orphan, PwD) sharing a branch with the general
  seat is a **separate, independently selectable entry** — never deduplicated or collapsed
  into the general-seat row, even though they share the same college/branch code.

### 1.7 CAP round selection
- Anywhere cutoffs or predictions are shown per CAP round (branch forecast, prediction
  results), the counsellor must be able to switch between the rounds that actually have
  data for that branch/prediction set (Round I–IV), and the displayed numbers must update
  to match the selected round. The currently-selected round must always be visually obvious.

---

## 2. Discover (Home) — `/`

**Purpose:** browse/search/filter all colleges; entry point into the rest of the app.

Must include:
- A headline search box that filters the visible college list by name/city/district.
- A branch/stream quick-filter (dropdown of real branch keywords from the data).
- Quick filter pills: All / Government / Private / NAAC A & Above — mutually exclusive
  with the sidebar's own institution-type and NAAC filters (selecting one supersedes the
  conflicting sidebar choice, never both applied contradictorily).
- A full filter sidebar: district, institution type, NAAC grade, branch, score range,
  cutoff-percentile range — each independently combinable, with a single "Clear all".
- A sort control: by Score or by Cutoff percentile.
- Each college row must show: rank position, name, city/institution-type/NAAC-grade
  summary, the metric currently being sorted by, a Compare toggle, and must be clickable
  through to that college's profile.
- Pagination via "Load more" (not silently truncated with no way to see the rest).
- Empty state ("no colleges matched") must offer a way to clear filters, not dead-end.
- A persistent call-to-action toward starting a student prediction ("Get predictions").
- Loading state must be a placeholder skeleton, not a blank screen.

---

## 3. College Profile — `/colleges/[code]`

**Purpose:** the full reference page for one physical college.

Must include, each independently allowed to be "not available" if the data doesn't exist:
- **Photo gallery** — at least a placeholder if no photos exist; a primary hero image plus
  thumbnails; clicking any image opens a full-size lightbox browsable across all photos.
- **Identity header**: college name, district, institution type, year established,
  official institute code (copyable) + any paired codes, NAAC grade badge, autonomous-status
  badge, overall quality score (out of 100), a "Top Placements" badge when placement rate
  is high.
- **AI-generated description** — if none exists yet, an explicit "generate" action; once
  generated, a "regenerate" action; must indicate if a counsellor has hand-edited it.
- **Quick facts strip**: established year, campus size (or "N/A"), affiliated university,
  NIRF rank (or "—").
- **Placements section**: placement rate, average package, highest package, top recruiters
  — or an explicit "not available" message. If the data is flagged unreliable/outdated,
  that warning must be visible, not hidden.
- **Fees section**: annual fee for each of GOPEN/GOBC/GSC/TFWS categories, or "Fee N/A" for
  categories/colleges without fee data.
- **Facilities section**: Wi-Fi, boys hostel, girls hostel, sports, campus size — each shown
  as present/absent, with absent shown distinctly (not simply omitted).
- **Photo gallery grid** (separate from the hero) when more than one photo exists.
- **Branches offered table**: one row per branch, each showing branch name (linked to that
  branch's forecast page), branch code (copyable), 2025 actual closing percentile, 2026
  predicted closing percentile, confidence badge, seat intake (general + TFWS combined
  where both exist), and a way to jump to the branch's full forecast.
- **Contact section**: address, website (external link), email, phone, Google Maps link —
  or "not available" if none exist.
- **Save/Bookmark action** — toggles this college's presence in the counsellor's Bookmarks,
  with visible confirmation feedback, reachable both from a sidebar (desktop) and a sticky
  bottom bar (mobile).
- **Add to Compare action**, same placement pattern as Save.
- A link back to Discover.

---

## 4. Branch Forecast — `/branches/[canonicalCode]`

**Purpose:** the deep-dive forecast for one specific branch at one college.

Must include:
- Branch name, parent college name (linked back to the college profile), canonical code.
- CAP round selector (only rounds with real data for this branch are offered).
- A summary strip: 2026 predicted close (with a calibrated likely-range, not a bare point
  number), 2025 actual close, seat intake (general + TFWS, or "not available"), and a
  3-year trend indicator paired with the confidence badge.
- A historical-vs-predicted bar chart for the open/general category across the years the
  branch has data for, visually distinguishing actual (historical) bars from the forecast
  bar, with a legend.
- The category tree (see §1.6) for closing percentiles by category across all historical
  years plus the 2026 forecast, for the selected CAP round.
- An explanatory note that 2026 figures are model forecasts to be verified against official
  rounds, and a note on where the seat-intake number comes from (or that it's unavailable).
- A link back to the parent college.

---

## 5. College Compare — `/compare`

**Purpose:** side-by-side comparison of 2–4 colleges.

Must include:
- The compare list must be shareable via URL (so a link with specific colleges reproduces
  the same comparison for anyone who opens it).
- A card per selected college (photo thumbnail, name linked to its profile, score, NAAC
  badge) plus a removal action per card.
- An "add college" slot (search-to-add) while fewer than 4 are selected.
- Below the minimum (2 colleges), the comparison table must not render — instead show a
  prompt to add more.
- Once ≥2 colleges are present, a full comparison broken into collapsible sections
  covering, at minimum: Overview (score, institution type, established, autonomous status,
  university, district), Accreditation (NAAC, NIRF, NBA), Admissions & Cutoffs (toughest
  branch, 2025 close, 2026 predicted close, branch count), Placements, Fees by category,
  Facilities, Location & Contact.
- A "highlight differences" toggle that visually marks rows where the compared colleges'
  values differ.
- Every comparison cell must stay aligned to the correct college's card column regardless
  of load order or a failed fetch for one college (a failed college shows a per-card error
  with a way to remove just that one, not break the whole comparison).

---

## 6. Student Profile Form — `/students/new`, `/students/[id]/edit`

**Purpose:** capture (or edit) the data the prediction engine needs for one student.

Must capture:
- Name, gender (optional).
- MHT-CET percentile (required, 0–100) — visually distinguished as the single most
  important field.
- JEE Main rank (optional), board percentage (optional).
- Category (required, from the live category list) and an optional category variant.
- Reserved-pool eligibility toggles, each explicit and student-declared (never inferred
  from another field): PwD (with a conditional PwD-type field when enabled), Defence,
  TFWS, Orphan, EWS.
- Family income bracket (optional) — informational only, must NOT drive EWS eligibility.
- Home district (from the live district list, plus an explicit "Other / not listed" option
  for out-of-state/All-India candidates).
- Branch preferences (multi-select from live branch keywords) and location preferences
  (multi-select).
- Maximum annual fee budget (optional; 0/blank = no limit).
- Free-text counsellor notes (optional).
- Submitting (create or edit) must take the counsellor straight to that student's
  prediction results, and any previously-cached predictions/shortlist for that student must
  be invalidated so the new numbers actually reflect the edit (an edit must never appear to
  "do nothing").

---

## 7. Prediction Results — `/students/[id]/results`

**Purpose:** show every branch the student could target, sorted into three confidence
bands, for a chosen CAP round.

Must include:
- Student name and percentile in the page header.
- CAP round selector (I–IV); switching re-runs the results for that round.
- Three bands, always in this order: **Safe**, **Probable**, **Reach** — each with its own
  one-line plain-language definition, a count of results and unique colleges, and a distinct
  visual identity per band that must remain consistent everywhere bands appear (results
  page, shortlist, badges).
- An empty band must say explicitly why it's empty in band-specific language (not a generic
  "no results"), and never silently disappear.
- Each result (college + branch + seat pool) must show: college name (linked to its
  profile), branch name and city (linked to the branch forecast), branch code, predicted
  closing percentile with its calibrated likely-range, margin (student percentile vs.
  predicted close), confidence badge (with a plain-language tooltip — first-year-of-round
  data must say so explicitly, not just "low confidence"), seat type, a fallback-data
  warning when seat data isn't an exact match, seat-pool badge when this is a reserved-pool
  entry, seat count, fee (or "Fee N/A"), and college quality score.
- Each result must have an "Add to shortlist" action with visible saved/unsaved state; a
  reserved-pool entry and the general entry for the same branch must be independently
  addable/removable.
- A way to expand any band into a full sortable table (sortable by predicted close, margin,
  or score), including bulk multi-select "add selected to shortlist".
- If branches were hidden for exceeding the student's fee budget, that count must be shown,
  along with how many fee-unknown branches were kept instead of hidden.
- A persistent floating bar showing the current shortlist count once non-empty, with a way
  to jump straight to the full shortlist.
- A link to edit the student profile, and a shortlist count/link, both reachable from this
  page's header at all times.
- Loading state = skeleton placeholders per band; zero-result state must suggest concrete
  next actions (loosen preferences, raise percentile, check category), not a dead end.

---

## 8. Student Shortlist — `/students/[id]/shortlist`

**Purpose:** the ranked preference list the counsellor builds for one student, to hand to
them / print.

Must include:
- Every saved entry showing: rank position, college name (linked), branch name, seat type,
  branch code, fee, reserved-pool badge (if applicable), college score, safety band badge,
  predicted percentile, and a remove action.
- Manual drag-to-reorder of the list, auto-saved on drop.
- Alternative sort options (by predicted percentile, by college score, by safety/band) that
  reorder and persist the list — but switching to a sort mode other than "manual" must be
  reversible back to manual ordering.
- A print action producing a clean, print-only layout (no navigation chrome) headed with
  the student's name, percentile, category, and district.
- Empty state must point back to the prediction results page to start adding entries.
- A reserved-pool entry and the general entry for the same branch must remain distinguishable
  and independently removable — never collapsed into one row.

---

## 9. Bookmarks (counsellor-level saved colleges) — `/my-shortlist`

**Purpose:** a counsellor's own saved-college list, independent of any specific student.

Must include:
- Every bookmarked college: name (linked to profile), city, institution type, score, and
  a remove action.
- Manual drag-to-reorder.
- A print action.
- Empty state pointing back to Discover.
- A call-to-action toward creating a student profile to get personalized (percentile-based)
  matches for the bookmarked colleges — bookmarks alone are not band-classified (no
  Safe/Probable/Reach) because they aren't tied to a student's percentile.

---

## 10. Students list (counsellor caseload) — `/students`

**Purpose:** manage all of a counsellor's student profiles.

Must include:
- Search by name/category/district, and sort by recently-updated / name / percentile.
- Each row: name, percentile, category, district, last-updated date, and quick actions to
  view predictions, edit, or delete.
- Delete must require an explicit confirm step (not a single click), inline per row.
- Empty state pointing to creating the first student profile.

---

## 11. Dashboard — `/dashboard`

**Purpose:** logged-in counsellor's home base.

Must include:
- Welcome header with the counsellor's name.
- Quick stats: number of saved (bookmarked) colleges, number of student profiles, account
  email, and a shortcut back to Discover.
- A preview (subset) of student profiles with a "view all" link when there are more than
  shown, and a "new profile" action, and an empty state pointing to creating one.
- A preview (subset) of bookmarked colleges with a link to the full Bookmarks page for
  reordering/printing, a remove action per item, and an empty state pointing to Discover.
- Requires login; unauthenticated visits redirect to Login (§1.2).

---

## 12. Login / Signup — `/login`, `/signup`

Must include:
- Login: email + password, inline validation errors, a server-error surface for failed
  auth, and a link to Signup.
- Signup: full name, email, password + confirm-password (must match), inline validation,
  a server-error surface, and a link to Login.
- Both: password visibility toggle.
- Successful auth logs the counsellor in and returns them to Discover, **except** when the
  visitor has pre-login bookmarks — then the merge prompt (§1.2) must appear before
  finishing login.
