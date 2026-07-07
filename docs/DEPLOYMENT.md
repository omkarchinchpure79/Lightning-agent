# Deploying EduPath

Everything runs on **Vercel**, free tier, as two projects sharing this repo:

| Project | What | Root |
|---|---|---|
| `edupath` | Next.js frontend | `web/` |
| `edupath-api` | FastAPI backend | repo root, entrypoint `api/index.py` |

Writable data (counselor accounts, students, shortlists — 5 tables) lives on
**Turso** (SQLite-over-HTTP, free tier) via `api/turso.py`, a zero-dependency
Hrana-v2 client — because Vercel's Python functions are serverless and have
no persistent disk. Read-only engine data (colleges, cutoffs, 122k
predictions — everything the pipeline in the main `CLAUDE.md` gate produces)
ships as `deploy/edupath.db.gz` (21MB gzip of the 99MB DB), unpacked to
`/tmp` on cold start by `api/_seed_runtime.py`. Every route either reads
engine data via `get_conn()` or writes/reads the 5 app tables via
`get_app_conn()` (`api/db.py`) — never mix the two for the same table.

## Current deployment

- Frontend: https://edupath-pied.vercel.app
- Backend: https://edupath-api-lime.vercel.app (health: `/api/health`)
- Both on the `edupath` Vercel team, linked via `.vercel/project.json` in
  each of repo-root (`edupath-api`) and `web/` (`edupath`).

## Redeploying

```bash
# Backend (repo root)
vercel --cwd "." deploy --prod --yes --scope edupath

# Frontend
vercel --cwd "web" deploy --prod --yes --scope edupath
```

**Gotcha — one vercel.json per git checkout, two projects.** Vercel's CLI
resolves `vercel.json` by walking up to the nearest `.git` root, not by cwd.
Both projects share this repo, so:
- root `vercel.json` declares the backend as a `services` block + a
  catch-all rewrite (`api/index.py` is a plain FastAPI entrypoint; the
  `services` framework is what Vercel auto-assigns to Python/FastAPI
  projects, and it REQUIRES the rewrite or every route 404s).
- `web/vercel.json` (`{"framework": "nextjs"}`) exists purely to shadow the
  root one when deploying the frontend — without it, the frontend deploy
  inherits the backend's `services` config and fails ("no services
  declared").
- If a project's Framework Preset ever gets stuck on "Services" after a bad
  deploy, `vercel project update <name> --framework other` resets it —
  the stored preset persists across deploys even after vercel.json changes.
- **Never run a deploy in the background without confirming it actually
  finished** — an interrupted CLI process can leave a deployment stuck
  "Building" server-side for the full timeout window, queuing every
  subsequent deploy behind it. Check `vercel ls --scope edupath` for a
  stuck `Building`/`Queued` entry and `vercel rm <url> --yes` it if found.

## Environment variables

**Backend** (`edupath-api` project, Vercel dashboard → Settings → Environment Variables):
- `JWT_SECRET` — required, signs counselor JWTs
- `TURSO_DATABASE_URL`, `TURSO_AUTH_TOKEN` — required for durable writes;
  provisioned via `vercel install tursocloud/database --scope edupath`
- `CORS_ORIGINS` — set to the frontend's Vercel URL
- `ANTHROPIC_API_KEY` — optional, only for AI college descriptions

**Frontend** (`edupath` project):
- `NEXT_PUBLIC_API_URL` — the backend's Vercel URL. Inlined at **build**
  time — changing it requires a redeploy (`vercel deploy --prod`), not just
  a dashboard save. Set with `vercel env add NEXT_PUBLIC_API_URL production`.

## Post-deploy checklist

Verified live end-to-end (2026-07-08, via real browser automation, not curl):
- [x] `/api/health` returns `{"status":"ok", ...}` with real college/prediction counts
- [x] Sign up a counsellor on the Vercel frontend URL
- [x] Create a student → SAFE/PROBABLE/REACH bands render with real predictions
- [x] Shortlist a result, reload the page — stays shortlisted (Turso write survives)

Re-run this checklist after any backend redeploy that touches `api/db.py`,
`api/turso.py`, or any route file.

## Updating shipped cutoff data later

New CAP round → run the pipeline gate (see main `CLAUDE.md`), then:

```bash
gzip -c db/edupath.db > deploy/edupath.db.gz
git commit -m "data: refresh seed DB (CAP 2026 R2)" deploy/edupath.db.gz
vercel --cwd "." deploy --prod --yes --scope edupath
```

This only refreshes the read-only engine snapshot — counselor accounts,
students, and shortlists live on Turso and are untouched.

## College photos (optional, 333MB)

Not bundled (way over the serverless payload limit). The frontend falls back
to placeholder art when `/static/images/...` 404s — everything else works
without them. If needed later, host `data/images/` on a CDN/object store and
change `web/lib/api.ts`'s image URL builder to point there instead of the
API's `/static/images`.

## Local dev is unaffected

No env vars required. `EDUPATH_DB_PATH` and `TURSO_DATABASE_URL` are both
unset locally, so `api/db.py` falls through to the normal `db/edupath.db`
file for both engine reads and app-table writes, exactly as before this
deployment work.
