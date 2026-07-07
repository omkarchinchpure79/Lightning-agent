# Deploying EduPath

Two pieces, two hosts:

| Piece | Host | Why |
|---|---|---|
| `web/` (Next.js) | **Vercel** | static + SSR frontend, free Hobby tier |
| `api/` (FastAPI + SQLite) | **Render** (or any Docker host with a persistent disk) | needs a real process + disk — counsellor/student/shortlist writes go into SQLite, which serverless hosts can't persist |

The 99MB database ships inside the repo as `deploy/edupath.db.gz` (21MB).
On first boot `deploy/start.sh` unpacks it onto the persistent disk at
`EDUPATH_DB_PATH` (default `/data/edupath.db`); after that the disk copy is the
source of truth and survives every redeploy.

## 1. Backend on Render (~$7/mo, the only recurring cost)

1. Push this repo to GitHub (already at `omkarchinchpure79/Lightning-agent`).
2. In the [Render dashboard](https://dashboard.render.com): **New + → Blueprint**,
   pick the repo. Render reads `render.yaml` and provisions:
   - a Docker web service built from `deploy/Dockerfile.api`
   - a 1GB persistent disk mounted at `/data`
   - a generated `JWT_SECRET`
3. Wait for the first deploy, note the URL, e.g. `https://edupath-api.onrender.com`.
4. Smoke-check: `https://edupath-api.onrender.com/api/health` → `{"status":"ok"}`.

## 2. Frontend on Vercel

1. Vercel dashboard → **Add New → Project** → import the GitHub repo.
2. Set **Root Directory = `web`** (critical — the Next.js app is not at repo root).
3. Add the environment variable (build-time, all environments):
   - `NEXT_PUBLIC_API_URL=https://edupath-api.onrender.com`
4. Deploy. Note the URL, e.g. `https://edupath.vercel.app`.

## 3. Close the CORS loop

Back in Render → the service → Environment:

- `CORS_ORIGINS=https://edupath.vercel.app` (comma-separate extras, e.g. a custom domain)

Save → Render redeploys. Done.

## 4. Post-deploy checklist

- [ ] `/api/health` returns ok
- [ ] Sign up a counsellor on the Vercel URL, log in
- [ ] Create a student → results show SAFE/PROBABLE/REACH bands
- [ ] Shortlist an entry, reload — it persists (proves disk writes stick)
- [ ] Redeploy the API once, log in again — account still exists (proves the
      disk seed guard works)

## Updating shipped cutoff data later

New CAP round → locally run the pipeline (gate in CLAUDE.md), then:

```bash
gzip -c db/edupath.db > deploy/edupath.db.gz   # refresh the seed
git commit -m "data: refresh seed DB (CAP 2026 R2)" deploy/edupath.db.gz
```

Then either merge live counsellor tables by hand, or — if no real users yet —
set `RESEED_DB=1` on Render for one deploy (OVERWRITES the disk DB, including
counsellor accounts) and remove it afterwards.

## College photos (optional, 333MB)

Not baked into the image. Zip `data/images/`, host it anywhere durable
(GitHub release asset works), set `SEED_IMAGES_URL=<zip url>` on Render.
Without it the frontend falls back to placeholder art — everything else works.

## Notes / gotchas

- `NEXT_PUBLIC_API_URL` is inlined at **build** time — changing it in Vercel
  requires a redeploy, not just a save.
- Render's free tier has no persistent disk; the starter paid instance is the
  cheapest safe option. Free-tier + no disk = all counsellor data lost on every
  restart.
- The API serves college images at `/static/images`; the frontend builds image
  URLs from `NEXT_PUBLIC_API_URL`, so no extra config is needed for them.
- Local dev is unchanged: no env vars needed, defaults still point at
  `db/edupath.db` and `localhost`.
