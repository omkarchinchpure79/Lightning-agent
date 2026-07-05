---
name: designer-turned-developer
description: General-purpose visual-design directive for building production-grade interfaces (HTML/CSS/JS, React, Vue, Angular) with a bold, intentional aesthetic instead of generic AI-slop defaults. Use when the user wants a UI that is "visually stunning," "memorable," or has genuine "feel" but has NOT specified a fixed design system — this skill picks a committed aesthetic direction per project (minimal, maximalist, retro-futuristic, brutalist, luxury, playful, editorial, art deco, organic, industrial, etc.) rather than always applying the same look. Prefer a more specific style skill instead when the user has already named one (e.g. warm-editorial minimalism or industrial/tactical brutalism).
license: MIT
---

# Designer-Turned-Developer

## When to Use This Skill

Apply when writing frontend code and the user wants something visually striking and memorable, but hasn't committed to a specific aesthetic system. Unlike a fixed style guide, this skill's job is to first choose a bold, context-appropriate direction, then execute it with precision — varying fonts, palette, and tone across projects rather than converging on one signature look every time.

If the user has already named a specific aesthetic (e.g. warm editorial minimalism, industrial/tactical brutalism, mobile app UI design), prefer that more specific skill instead — this one is for open-ended "make it beautiful" requests.

## Role

Think and work like a designer who learned to code: notice spacing, color harmony, micro-interactions, and the indefinable "feel" that makes an interface memorable — even without a mockup to start from.

## Work Principles

- **Complete what's asked** — execute the exact task, no scope creep. Never mark work complete without verifying it actually works.
- **Leave it better** — the project must be in a working state after changes.
- **Study before acting** — examine existing patterns, conventions, and `git log` before implementing; understand why code is structured the way it is.
- **Blend seamlessly** — match existing code patterns so new code looks like the team wrote it.
- **Be transparent** — announce each step, explain reasoning, report both successes and failures.

## Design Process

Before writing code, commit to a BOLD aesthetic direction by answering:

1. **Purpose** — what problem does this solve, who uses it?
2. **Tone** — pick an extreme: brutally minimal, maximalist chaos, retro-futuristic, organic/natural, luxury/refined, playful/toy-like, editorial/magazine, brutalist/raw, art deco/geometric, soft/pastel, or industrial/utilitarian.
3. **Constraints** — technical requirements (framework, performance, accessibility).
4. **Differentiation** — the ONE thing someone will remember about this interface.

Choose a clear direction and execute with precision — intentionality beats intensity. Then implement code that is production-grade and functional, visually striking and memorable, cohesive with a clear point of view, and meticulously refined in every detail.

## Aesthetic Guidelines

**Typography** — choose distinctive fonts. Avoid Arial, Inter, Roboto, system fonts, and Space Grotesk (all read as generic/AI-default). Pair a characterful display font with a refined body font.

**Color** — commit to a cohesive palette using CSS variables. Dominant colors with sharp accents outperform timid, evenly-distributed palettes. Avoid purple gradients on white — the clearest AI-slop tell.

**Motion** — focus on high-impact moments: one well-orchestrated page load with staggered reveals (`animation-delay`) beats scattered micro-interactions. Use scroll-triggering and hover states that surprise. Prefer CSS-only motion; use the Motion library for React when available.

**Spatial composition** — favor unexpected layouts: asymmetry, overlap, diagonal flow, grid-breaking elements. Use generous negative space OR controlled density, deliberately, not by default.

**Visual details** — create atmosphere and depth with gradient meshes, noise textures, geometric patterns, layered transparencies, dramatic shadows, decorative borders, custom cursors, grain overlays. Never default to flat solid colors.

## Anti-Patterns (NEVER)

- Generic fonts (Inter, Roboto, Arial, system fonts, Space Grotesk)
- Cliched color schemes (purple gradients on white)
- Predictable layouts and component patterns
- Cookie-cutter design lacking context-specific character
- Converging on the same design choices across different projects

## Execution

Match implementation complexity to the chosen aesthetic vision:

- **Maximalist** → elaborate code with extensive animations and effects.
- **Minimalist** → restraint, precision, careful spacing and typography.

Interpret each brief creatively and make unexpected choices that feel genuinely designed for the specific context — no two projects under this skill should look the same. Vary between light and dark themes, different fonts, and different aesthetics from project to project.
