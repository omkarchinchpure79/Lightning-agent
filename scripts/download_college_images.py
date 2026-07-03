"""
download_college_images.py — one-time batch download of Google Maps campus
photos (gps-cs-s URLs) to local storage, so the app never depends on
hotlinking Google's CDN at page-load time (which Chrome blocks via Referer
once a page embeds the image — see referrerPolicy stopgap in the frontend
for the immediate fix; this script is the permanent one).

Downloads up to MAX_PER_COLLEGE images per college into data/images/{code}/,
then writes the resulting relative paths into a new
college_details.local_image_paths column (JSON array), leaving image_urls/
image_metadata untouched for provenance.

Idempotent: skips colleges that already have local_image_paths populated
and files present on disk. Safe to re-run after interruption.

Usage:
    python scripts/download_college_images.py
"""
import json
import os
import re
import sqlite3
import time
import urllib.error
import urllib.request

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(_ROOT, "db", "edupath.db")
IMAGES_DIR = os.path.join(_ROOT, "data", "images")

MAX_PER_COLLEGE = 5
REQUEST_DELAY_SEC = 0.3
TIMEOUT_SEC = 10
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"
)


def _norm_size(url: str) -> str:
    """Normalise Google photo size params to a gallery-friendly size."""
    return re.sub(r"=w\d+-h\d+.*", "=w800-h600-k-no", url)


def _ensure_column(conn: sqlite3.Connection) -> None:
    cols = [c[1] for c in conn.execute("PRAGMA table_info(college_details)").fetchall()]
    if "local_image_paths" not in cols:
        conn.execute("ALTER TABLE college_details ADD COLUMN local_image_paths TEXT")
        conn.commit()


def _download_one(url: str, dest_path: str) -> bool:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT_SEC) as resp:
            data = resp.read()
        with open(dest_path, "wb") as f:
            f.write(data)
        return True
    except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError) as e:
        print(f"    FAIL {url[:70]}... -> {e}")
        return False


def main():
    os.makedirs(IMAGES_DIR, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    _ensure_column(conn)

    rows = conn.execute(
        "SELECT college_code, image_urls, local_image_paths FROM college_details "
        "WHERE image_urls LIKE '%gps-cs-s%'"
    ).fetchall()

    total = len(rows)
    done = skipped = failed_colleges = 0
    total_images_downloaded = 0

    for i, row in enumerate(rows, 1):
        code = row["college_code"]
        existing = row["local_image_paths"]

        # Idempotent skip: already has local paths AND the files are on disk.
        if existing:
            try:
                paths = json.loads(existing)
                if paths and all(
                    os.path.exists(os.path.join(IMAGES_DIR, p)) for p in paths
                ):
                    skipped += 1
                    continue
            except (json.JSONDecodeError, TypeError):
                pass

        urls = json.loads(row["image_urls"])
        campus_urls = [u for u in urls if isinstance(u, str) and "gps-cs-s" in u][:MAX_PER_COLLEGE]
        if not campus_urls:
            continue

        college_dir = os.path.join(IMAGES_DIR, code)
        os.makedirs(college_dir, exist_ok=True)

        saved_paths = []
        for idx, url in enumerate(campus_urls):
            dest = os.path.join(college_dir, f"{idx}.jpg")
            rel_path = f"{code}/{idx}.jpg"
            if os.path.exists(dest):
                saved_paths.append(rel_path)
                continue
            ok = _download_one(_norm_size(url), dest)
            if ok:
                saved_paths.append(rel_path)
                total_images_downloaded += 1
            time.sleep(REQUEST_DELAY_SEC)

        if saved_paths:
            conn.execute(
                "UPDATE college_details SET local_image_paths = ? WHERE college_code = ?",
                (json.dumps(saved_paths), code),
            )
            conn.commit()
            done += 1
        else:
            failed_colleges += 1

        if i % 25 == 0 or i == total:
            print(f"  [{i}/{total}] done={done} skipped={skipped} failed_colleges={failed_colleges} "
                  f"images_downloaded={total_images_downloaded}")

    conn.close()
    print(f"\nComplete. {done} colleges downloaded, {skipped} already had local images, "
          f"{failed_colleges} colleges failed entirely. {total_images_downloaded} image files saved.")


if __name__ == "__main__":
    main()
