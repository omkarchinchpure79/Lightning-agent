# Handoff: EduPath — "The Path" redesign (light mode)

## Overview
A full visual redesign of the EduPath MHT-CET counsellor app. Every existing route is
restyled into one consistent system — **"The Path"** — named after the product logo
(a bezier curve from a green anchor point to a blue destination ring = a student's path
from percentile to seat). This handoff covers **light mode only**; dark mode is a later pass
(the tokens are left in place so it doesn't break).

## About the design files
`EduPath Full Redesign.dc.html` is a **design reference created in HTML** — a prototype of the
intended look, laid out as one canvas with all 10 screens in flow order. It is **not** production
code to copy verbatim. The task is to **recreate these screens inside the existing Next.js + Tailwind
app**, reusing its established patterns (`--ep-*` CSS variables, shadcn-style UI components,
lucide icons, framer-motion, react-query). Open the HTML file in a browser to see pixel-level
spacing, color, and type for every screen.

The `code/` folder contains **three finished drop-in files** that do the global reskin — paste them
in first; they re-theme the entire app before you touch a single page.

## Fidelity
**High-fidelity.** Colors, typography, spacing, and radii are final. Match them exactly.

---

## Start here: the 3 global files (in `code/`)
Applying these re-skins ~80% of the app instantly, because every screen already reads from the
`--ep-*` tokens and shares `NavHeader`.

1. **`code/app/globals.css`** → replace `web/app/globals.css`
   - New warm-paper semantic tokens (`--ep-bg #F4F1EA`, `--ep-surface #FBFAF6`, `--ep-text #14213A`,
     `--ep-border #E4DFD2`, warm `--color-ep-muted #8A867B`).
   - New type tokens wired to next/font: `--font-sans` (Public Sans), `--font-serif` (Newsreader),
     `--font-display` (Instrument Serif), `--font-mono` (IBM Plex Mono).
   - Adds `.font-display / .font-serif / .font-mono` helpers and `-ink` color tokens for text on
     green/amber/red tints. Card radius bumped to 13px.

2. **`code/app/layout.tsx`** → replace `web/app/layout.tsx`
   - Loads the four Google fonts via `next/font/google` and exposes them as CSS variables on `<html>`.
   - Drops the old `Inter` import.

3. **`code/components/NavHeader.tsx`** + **`code/components/EduPathLogo.tsx`**
   - `NavHeader` swaps the scraped PNG logo for the inline `<EduPathLogo/>` (bezier mark + Instrument
     Serif wordmark) and turns the identity chip into a circular initials avatar. `EduPathLogo` /
     `EduPathMark` are new files — add them to `web/components/`.
   - Because the mark is inline SVG using `currentColor`/tokens, the `/logo-light.png` +
     `/logo-dark.png` `<img>`s on the **login** and **signup** pages can be replaced with
     `<EduPathLogo size={40} />` too.

After these four files, do the per-screen structural work below.

---

## Global rules applied on every screen
- **No emoji, anywhere.** Replace every emoji (🎓 💼 🏛️ 🎯 🌟 ⭐ �Print 🖨️ 📊 💰 ✨ 💡 etc.) with a
  lucide icon or a typographic label. Filter pills, badges, section titles, CTAs, empty states — all.
- **Headings** use `font-display` (Instrument Serif), sizes 28–58px, weight 400, `letter-spacing:-0.01em`.
- **College / branch names** in lists use `font-serif` (Newsreader), 14–19px, weight 500.
- **All numbers, codes, %iles, fees, dates, labels** use `font-mono` (IBM Plex Mono).
- **Body / UI** stays Public Sans.
- **Signal system:** SAFE = green `#2EB870` (ink `#1E7A46`, tint `#E7F4EC`), PROBABLE = amber
  `#D9A441` (ink `#B0952E`, tint `#F5EBD3`), REACH = red `#C75450` (ink `#B23F3B`, tint `#F8E1DF`).
  Used on band cards, confidence badges, shortlist band tags, and the anchor dots in lists.
- **Anchor dots:** a 9px filled dot preceding list rows — green for the top/safe item, blue `#1E4D8C`
  otherwise. This is the recurring "path" motif; also used as dotted SVG curves behind heroes.
- **Cards:** `background var(--ep-surface)`, `border 1px var(--ep-border)`, radius 13px, no heavy shadows.

---

## Screens
Screen IDs (2a–2j) match the badges in the HTML reference. Route paths are the existing ones.

### 2a — Login  ·  `/login`
- **Layout:** centered column, max-width ~460px. Dotted bezier curve SVG behind the card
  (`stroke #DED8CA, stroke-width 2, stroke-dasharray "2 9"`).
- **Components:** `<EduPathLogo size={40}/>` centered → mono caption "MHT CET COUNSELLOR PORTAL"
  (letter-spacing .14em, `#9A968B`). Card (`#FBFAF6`, border `#E4DFD2`, radius 16px, padding 30px):
  Email + Password fields (`#F4F1EA` fill, border `#DCD6C8`, radius 10px), "Forgot?" link in
  primary blue, eye toggle icon. Submit = solid `#1E4D8C`, white, "Log in" + arrow icon. Footer link
  "Create one" in primary. Keep the existing shortlist-merge dialog; just restyle to these tokens.

### 2b — Signup  ·  `/signup`
- Same shell as login. Heading "Start your path" (Instrument Serif). Fields: Full name, Email,
  Password + Confirm (two-up). Submit "Create account" + plus icon.

### 2c — Discover (home)  ·  `/`
- **Hero:** dotted bezier curve behind. Mono eyebrow "GUIDANCE PLATFORM · MHT CET" in green.
  H1 (Instrument Serif, 58px): "Every student has a **path**. We help you find it." — "path." is
  italic + primary blue. Sub in Public Sans `#5B6472`. Search as an **underlined input row**
  (bottom border `1.5px #14213A`, search icon, placeholder, "Explore →"), not a boxed bar.
  Stat row: `713 colleges · 11 yrs cutoff data · 36 districts` (numbers in mono).
- **Filter chips:** pill row, real lucide icons (Landmark/Government, Building/Private, Star/NAAC).
  Active = primary border + `rgba(30,77,140,.06)` fill. "Coming soon" chips = dashed border + small
  mono `SOON` tag. Right-aligned "Sort ▾ Closing %ile".
- **College list = editorial rows, NOT image cards.** Each row: index number (Instrument Serif,
  `#B7B1A2`, 40px col) · anchor dot · name (Newsreader 19px) + meta line (`city · type · NAAC`) ·
  right-aligned **Closing %ile** (mono 20px) + mono uppercase label · **fee** (mono) · chevron.
  Divider `1px #E4DFD2` between rows. This replaces the current `CollegeCard` grid + scraped
  thumbnails entirely — no images.
- **Predictor CTA band:** full-width dark `#14213A` panel, faint dotted curve, serif headline
  "Ready for personalised matches?", green `#2EB870` button "Get predictions →".

### 2d — College profile  ·  `/colleges/[code]`
- Back link (chevron). **Hero mosaic:** CSS grid, 1 large tile (2×2) + 4 small + a "+N more" tile
  (`linear-gradient(135deg,#1E4D8C,#14213A)`, white label). Tiles are warm placeholder gradients
  with a faint building glyph — the existing `HeroGallery`/lightbox logic stays; only the styling and
  the empty/broken-image fallback change (warm gradient, not a hard grey).
- **Title block:** H1 Newsreader/Instrument 38px, location line with pin icon, badge cluster
  (NAAC pill green tint, "Autonomous" neutral pill, score pill with star).
- **About card:** header row with a lightbulb-free label "About this college" + green idea icon,
  "↺ Regenerate" text button; body in Newsreader 14.5px. (Keep the Claude generate/regenerate logic.)
- **Quick facts:** 4-col bordered strip (Established / Autonomous / University / NIRF), values in mono.
- **Placements + Fees:** two cards side by side; placement stats in mono 22px; fee-by-category rows
  (GOPEN/GOBC/GSC/TFWS) with mono amounts.
- **Facilities:** chips — present = green-tint border, absent = muted dashed at 60% opacity, lucide icons.
- **Branches table:** columns Branch (Newsreader/primary link) · 2026 pred. close (mono) · Confidence
  (green/amber tint badge). Links to `/branches/[canonicalCode]`.
- **Sticky right sidebar (280px):** "Save to shortlist" (solid primary) · "Visit website" · "View on
  Maps" (outline) · "View your full shortlist →". Keep the toast + mobile bottom bar.

### 2e — Branch deep-dive  ·  `/branches/[canonicalCode]`
- Back link. Mono eyebrow "BRANCH FORECAST" green. H1 branch name (Instrument Serif) + college/canonical
  sub. **Summary strip:** 3-col (2026 predicted close mono 26px · 3-yr trend with up/down arrow colored
  by direction · confidence badge).
- **Chart:** the existing recharts `BarChart` — restyle bars to `#C6D2DF` for historical and
  `#1E4D8C` for the `2026*` forecast bar; value labels in mono; keep the legend (Historical / 2026
  forecast). The HTML shows an SVG mock of the target look.
- **Category table:** Category · 2023 · 2024 · 2025 · **2026\*** (2026 column header + values in primary
  blue). Footnote in muted about forecasts. Values mono.

### 2f — Dashboard  ·  `/dashboard`
- H1 "Welcome back, {firstName}" (Instrument Serif 32px) + muted sub.
- **Stat cards:** Saved colleges, Student profiles (both mono numerals + lucide icon), Account (email),
  and a dashed "Discover colleges" action card.
- **Student profiles list:** rows with circular Instrument-Serif initial avatar (`#EDEAE1` bg, primary
  initial), name (Public Sans 600), mono meta `96.40% · OBC · Pune`, chevron. Link → `/students/[id]/results`.
- **My shortlist list:** rows with anchor dot + Newsreader name + mono score `92/100`.
- Section actions ("+ New profile", "Reorder & print →") as primary text links. **Note:** the reference
  fixes an existing bug — one row used `justify-content:between` (invalid); use `space-between`.

### 2g — New-student intake  ·  `/students/new` (via `StudentForm`)
- H1 "New student" + sub. Form in bordered section cards (Personal / Academic scores / Category &
  eligibility / Branch preferences / …), each with a `12px 18px` header row (Public Sans 600) and
  `#FBFAF6` body. Inputs `#F4F1EA` fill; the **focused/required** field gets a `1.5px #1E4D8C` border +
  white fill (see the %ile field). Toggles = pill switches (green when on). Branch prefs = selectable
  chips (selected = primary border + tint + check). Footer: outline "Cancel" + green
  "Create & run predictions →". Keep all react-hook-form/zod logic; restyle the shadcn Card/Input/
  Select/Switch/Checkbox to these tokens.

### 2h — Prediction results  ·  `/students/[id]/results`  ★ core screen
- H1 "Prediction results" (Instrument Serif) + mono context line (`CAP Round 1 · OBC · Home university…`).
- **Three band columns** (SAFE / PROBABLE / REACH). Each: colored header (tint bg + colored dot + ink
  label + mono "N across M colleges"), a one-line description, then result cards:
  - card = white, border `#E4DFD2`, radius 10px; name in Newsreader/primary; branch·city sub;
    a Saved (green outline "✓ Saved") **or** Add (outline + plus icon) button; two mono badges
    (confidence tint + seat-type neutral); footer `Close: 94.10   Margin: +2.30` (margin green if ≥0,
    red if <0). "View all N in table →" link.
- Keep the existing expand-to-full-width sortable `BandTable`, multi-select add, and framer stagger —
  restyle headers/badges to the signal tints.

### 2i — Student shortlist  ·  `/students/[id]/shortlist`
- H1 "Shortlist" + mono `name · N saved options`. "Print" = outline button with printer icon (no emoji).
  Numbered rows (Instrument Serif index) with Newsreader name, mono meta (`branch · seat · fee`), a band
  tag (green/amber/red tint), and mono predicted close. Keep the print stylesheet.

### 2j — Global "My Shortlist"  ·  `/my-shortlist`
- H1 "Your Shortlist" with a filled-heart icon; green "Get predictions →" button. Sub `N colleges saved ·
  drag to reorder priority`. Rows: drag-handle (grip icon) · anchor dot · Newsreader name + meta · mono
  score · trash icon. Keep framer `Reorder.Group`. Restyle empty state (no 💜) — heart icon + copy.

---

## Interactions & behavior (unchanged — keep all existing logic)
- Auth (login/signup/merge dialog), react-query fetching, shortlist localStorage + server sync,
  framer-motion band stagger + card hovers, results table sort/multi-select, drag-to-reorder,
  print, Claude description generate/regenerate. **Only styling changes**, except the emoji→icon
  swaps and the Discover card-grid → editorial-list restructure.
- Hover: list rows lift subtly / darken border; buttons `hover:opacity-90`. Keep 150–200ms easing.

## Design tokens (quick reference)
- **Paper/bg** `#F4F1EA` · **surface** `#FBFAF6` · **ink** `#14213A` · **secondary** `#3E4757` ·
  **muted** `#8A867B` · **border** `#E4DFD2` · **border-strong** `#DCD6C8`
- **Primary** `#1E4D8C` (dark `#163A6B`) · **green** `#2EB870`/ink `#1E7A46`/tint `#E7F4EC` ·
  **amber** `#D9A441`/ink `#B0952E`/tint `#F5EBD3` · **red** `#C75450`/ink `#B23F3B`/tint `#F8E1DF`
- **Placeholder gradients** (college tiles): `#DCE3EC→#C6D2DF` (cool) and `#E3E0D6→#D4CFC0` (warm).
- **Radius** cards 13px, inputs/buttons 10px, pills 999px. **Fonts** as above.

## Assets
- Logo is now **inline SVG** (`EduPathLogo.tsx`) — the `/logo-*.png` files can be retired from the UI
  (keep favicons). No new image assets required; college photos use the existing gallery data with
  warm gradient fallbacks.

## Files in this bundle
- `EduPath Full Redesign.dc.html` — the design reference (open in a browser). `support.js` is its runtime.
- `code/app/globals.css`, `code/app/layout.tsx`, `code/components/NavHeader.tsx`,
  `code/components/EduPathLogo.tsx` — drop-in production files.
