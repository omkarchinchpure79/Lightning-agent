# Deployment

Two separate deployments: the Next.js frontend (`web/`) on Vercel, and the FastAPI
backend (`api/` + `scripts/`/`app/` + SQLite) on a host with a **persistent disk**.
Vercel's serverless functions have an ephemeral, read-only filesystem — they cannot
run this backend (every write — signup, student save, shortlist — would be lost on
the next cold start).

## 1. Backend — needs persistent disk (Railway, Render paid tier, Fly.io, or a VPS)

The API is a plain FastAPI app; it imports from the repo root (`app/`, `scripts/`),
so the working directory at runtime must be the **repo root**, not `api/`.

- **Start command:** `uvicorn api.main:app --host 0.0.0.0 --port $PORT`
- **Persistent volume/disk** must cover, relative to repo root:
  - `db/` — holds `edupath.db`
  - `data/images/` — locally-downloaded college photos served at `/static/images`
- **Required env vars** (see `.env.example`):
  - `JWT_SECRET` — generate with `python -c "import secrets; print(secrets.token_hex(32))"`
  - `ALLOWED_ORIGINS` — the deployed frontend's origin, e.g. `https://edupath.vercel.app`
    (comma-separate if there's more than one, e.g. a preview + production URL)
  - `ANTHROPIC_API_KEY` — optional, only needed for the "Generate description" AI feature
- **Seed the database once, manually.** `db/edupath.db` (~99 MB) and `data/images/`
  are gitignored on purpose (see root `CLAUDE.md`) — a fresh clone/deploy starts with
  an empty schema and no colleges. After first deploy, either:
  - upload the existing local `db/edupath.db` to the host's persistent volume, or
  - re-run the full pipeline on the server (`download_pdfs.py` → `parse_cutoffs.py` →
    `load_db.py` → the verification-gate scripts in root `CLAUDE.md` → `download_college_images.py`
    / `download_seat_intake_pdfs.py` + `parse_seat_intake.py`) — this takes ~20-30 min
    and needs network access to `fe2025.mahacet.org`.
  There is currently no automated seed/restore script — copying the file is the fast path.

## 2. Frontend — Vercel

- **Root Directory** (Vercel project setting): `web`
- **Framework preset:** Next.js (auto-detected)
- **Env var:** `NEXT_PUBLIC_API_URL` = the backend's public URL (e.g.
  `https://edupath-api.up.railway.app`) — read in `web/lib/api.ts`; defaults to
  `http://localhost:8000` if unset, which is wrong in production.
- No `vercel.json` needed — zero-config Next.js deploy.

## 3. After both are live

1. Confirm `ALLOWED_ORIGINS` on the backend matches the exact Vercel URL (scheme +
   host, no trailing slash) — a mismatch here is the #1 cause of "can't connect to
   the prediction engine" in production; it's a silent CORS rejection, not a 4xx/5xx.
2. Smoke-test: signup → login → Discover loads real colleges → a student prediction
   runs → shortlist print produces the choice-code table (see
   `docs/ui_rules.md` for the full behavior checklist).
3. `web/middleware.ts` hard-gates every route except `/login`/`/signup` behind the
   `edupath_token` cookie — confirm login actually sets it (DevTools → Application →
   Cookies) if anything 404s/redirect-loops right after deploy.
