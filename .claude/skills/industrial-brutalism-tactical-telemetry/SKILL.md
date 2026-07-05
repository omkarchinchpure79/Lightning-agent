---
name: industrial-brutalism-tactical-telemetry
description: Frontend design directive for architecting high-density, utilitarian web interfaces that synthesize mid-century Swiss typographic design, industrial manufacturing manuals, and retro-futuristic aerospace/military terminal HUDs. Use when writing or reviewing frontend code (HTML/React/Vue/Tailwind) and the user wants a raw, mechanical, "blueprint" or "terminal/HUD" aesthetic — rigid modular grids, extreme typographic scale contrast, monospace telemetry data, ASCII framing, simulated CRT scanlines/halftone/dithering, and a strictly utilitarian color palette (off-white+carbon+hazard-red, or dark CRT+phosphor+hazard-red). Not for soft, rounded, or conventional consumer SaaS UI.
license: MIT
---

# Industrial Brutalism & Tactical Telemetry UI

## When to Use This Skill

Apply when writing or reviewing frontend code (HTML, React, Vue, Tailwind) where the goal is a raw, mechanically precise, high-data-density interface — think Swiss industrial print manuals or a military/aerospace terminal HUD, not a conventional consumer SaaS product. Use when the user asks for "brutalist," "industrial," "terminal," "HUD," "tactical," or explicitly rejects soft/rounded consumer UI patterns.

This is a distinct visual language from soft editorial/minimalist skills (e.g. `premium-utilitarian-minimalism`) — do not blend the two. This system favors 90-degree corners, visible grid lines, monospace data, and simulated analog degradation over warm palettes and diffuse shadows.

## Visual Archetypes — Pick ONE Per Project

Two visual paradigms exist. Commit to one; never alternate or mix both within the same interface.

**Swiss Industrial Print** — 1960s corporate identity systems / heavy machinery blueprints. Light mode only: high-contrast newsprint/off-white substrate, monolithic heavy sans-serif type, unforgiving structural grids with visible dividing lines, aggressive asymmetric negative space, oversized viewport-bleeding numerals/letterforms, primary red as the sole alert/accent color.

**Tactical Telemetry & CRT Terminal** — classified military databases, legacy mainframes, aerospace HUDs. Dark mode exclusivity: high-density tabular data, absolute dominance of monospace type, technical framing devices (ASCII brackets, crosshairs), simulated hardware limitations (phosphor glow, scanlines, low bit-depth rendering).

## Typographic Architecture

Typography is the primary structural and decorative infrastructure — imagery is secondary. The system demands extreme variance in scale, weight, and spacing.

**Macro-typography (structural headers)** — Neo-grotesque/heavy sans-serif: `Neue Haas Grotesk (Black)`, `Inter (Extra Bold/Black)`, `Archivo Black`, `Roboto Flex (Heavy)`, `Monument Extended`.
- Scale: massive, fluid — `clamp(4rem, 10vw, 15rem)`.
- Tracking: extremely tight, often negative (`-0.03em` to `-0.06em`) so glyphs form solid architectural blocks.
- Leading: highly compressed (`0.85` to `0.95`).
- Casing: exclusively uppercase.

**Micro-typography (data & telemetry)** — Monospace/technical sans: `JetBrains Mono`, `IBM Plex Mono`, `Space Mono`, `VT323`, `Courier Prime`.
- Scale: fixed, small (`10px`–`14px` / `0.7rem`–`0.875rem`).
- Tracking: generous (`0.05em` to `0.1em`) to simulate typewriter/terminal matrix spacing.
- Leading: standard to tight (`1.2` to `1.4`).
- Casing: exclusively uppercase — used for all metadata, navigation, unit IDs, and coordinates.

**Textural contrast (artistic disruption)** — High-contrast serif: `Playfair Display`, `EB Garamond`, `Times New Roman`. Used exceedingly sparingly, and only after heavy post-processing (halftone filters, 1-bit dithering) to degrade vector perfection and create textural juxtaposition against the clean sans-serifs.

## Color System

Uncompromising. Gradients, soft drop shadows, and modern translucency are strictly prohibited — colors simulate physical media or primitive emissive displays. Choose ONE substrate palette per project; never mix light and dark substrates in the same interface.

**Swiss Industrial Print (light)**
- Background: `#F4F4F0` or `#EAE8E3` (matte, unbleached documentation paper)
- Foreground: `#050505`–`#111111` (carbon ink)
- Accent: `#E61919` / `#FF2A2A` (aviation/hazard red) — the ONLY accent color, used for strike-throughs, thick structural dividing lines, or vital data highlights

**Tactical Telemetry (dark)**
- Background: `#0A0A0A` or `#121212` (deactivated CRT — avoid pure `#000000`)
- Foreground: `#EAEAEA` (white phosphor) — primary text color
- Accent: `#E61919` / `#FF2A2A` (same hazard red, same rules)
- Terminal green `#4AF626`: optional, use ONLY for one specific element (e.g. a single status indicator or data readout) — never as general text color; omit entirely if it has no clear purpose

## Layout and Spatial Engineering

The layout must appear mathematically engineered — reject conventional web padding in favor of visible compartmentalization.

- **Blueprint grid**: strict CSS Grid. Elements are anchored precisely to grid tracks and intersections, never floated.
- **Visible compartmentalization**: extensive solid borders (1px or 2px solid) delineate distinct information zones; horizontal rules span the full container width to segregate operational units.
- **Bimodal density**: oscillate between extreme data density (tightly packed monospace metadata) and vast expanses of calculated negative space framing macro-typography.
- **Geometry**: absolute rejection of `border-radius` — all corners exactly 90 degrees.

## UI Components and Symbology

Standard web UI conventions are replaced with utilitarian, industrial graphic elements.

- **Syntax decoration**: ASCII characters framing data points — `[ DELIVERY SYSTEMS ]`, `< RE-IND >`, directional markers `>>>`, `///`, `\\\`.
- **Industrial markers**: `®`, `©`, `™` used as structural geometric elements, not legal text.
- **Technical assets**: crosshairs (`+`) at grid intersections, repeating vertical lines (barcodes), thick horizontal warning stripes, randomized string data (`REV 2.6`, `UNIT / D-01`) to simulate active mechanical processes.

## Textural and Post-Processing Effects

Simulated analog degradation prevents the design from reading as purely digital.

- **Halftone / 1-bit dithering**: transform continuous-tone images or large serif type into dot-matrix patterns via pre-processing or `mix-blend-mode: multiply` overlays combined with SVG radial dot patterns.
- **CRT scanlines**: for terminal interfaces, `repeating-linear-gradient` on the background to simulate horizontal electron-beam sweeps, e.g. `repeating-linear-gradient(0deg, transparent, transparent 2px, rgba(0,0,0,0.1) 2px, rgba(0,0,0,0.1) 4px)`.
- **Mechanical noise**: a global, low-opacity SVG static/noise filter applied to the DOM root for unified physical grain across both modes.

## Web Engineering Directives

- **Grid determinism**: `display: grid; gap: 1px;` with contrasting parent/child background colors generates mathematically perfect, razor-thin dividing lines without complex border declarations.
- **Semantic rigidity**: build the DOM with precise semantic tags (`<data>`, `<samp>`, `<kbd>`, `<output>`, `<dl>`) to reflect the technical nature of the telemetry.
- **Typography clamping**: use CSS `clamp()` exclusively for macro-typography so massive text scales aggressively while staying structurally sound across viewports.
