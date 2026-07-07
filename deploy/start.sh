#!/bin/sh
# EduPath API container entrypoint.
#
# First boot: seeds the persistent disk ($EDUPATH_DB_PATH, e.g. /data/edupath.db)
# from the gzipped snapshot baked into the image, so counsellor/student writes
# survive redeploys. Later deploys find the DB already present and leave it
# alone — refresh it deliberately with RESEED_DB=1 if you shipped new cutoff
# data (this OVERWRITES the disk copy, including counsellor accounts, so only
# do it before real users exist or after exporting their tables).
set -e

: "${EDUPATH_DB_PATH:=/data/edupath.db}"
export EDUPATH_DB_PATH
SEED=/srv/deploy/edupath.db.gz

if [ ! -f "$EDUPATH_DB_PATH" ] || [ "$RESEED_DB" = "1" ]; then
  if [ -f "$SEED" ]; then
    echo "Seeding database -> $EDUPATH_DB_PATH"
    mkdir -p "$(dirname "$EDUPATH_DB_PATH")"
    gunzip -c "$SEED" > "$EDUPATH_DB_PATH"
  else
    echo "WARNING: no seed snapshot at $SEED and no DB at $EDUPATH_DB_PATH" >&2
  fi
fi

# Optional: college photos. 333MB, so they are not baked into the image.
# Point SEED_IMAGES_URL at a zip (e.g. a GitHub release asset) to fetch once.
if [ -n "$SEED_IMAGES_URL" ] && [ ! -d /srv/data/images ]; then
  echo "Downloading college images..."
  mkdir -p /srv/data
  curl -fsSL "$SEED_IMAGES_URL" -o /tmp/images.zip
  unzip -q /tmp/images.zip -d /srv/data/
  rm -f /tmp/images.zip
fi

exec uvicorn api.main:app --host 0.0.0.0 --port "${PORT:-8000}"
