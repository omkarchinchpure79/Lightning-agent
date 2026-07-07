"""
_seed_runtime.py — serverless cold-start bootstrap. Imported FIRST by api.main.

On Vercel the repo filesystem is read-only and the 99MB engine DB ships as a
21MB gzip (deploy/edupath.db.gz). Unpack it to /tmp once per instance and
point EDUPATH_DB_PATH at it BEFORE api.db / engine_adapter resolve the path.
Locally (no VERCEL env var) this module does nothing.
"""
import gzip
import os
import shutil

if os.environ.get("VERCEL") and not os.environ.get("EDUPATH_DB_PATH"):
    _ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    _SEED = os.path.join(_ROOT, "deploy", "edupath.db.gz")
    _TMP_DB = "/tmp/edupath.db"
    if not os.path.exists(_TMP_DB) and os.path.exists(_SEED):
        _partial = _TMP_DB + ".partial"
        with gzip.open(_SEED, "rb") as src, open(_partial, "wb") as dst:
            shutil.copyfileobj(src, dst)
        os.replace(_partial, _TMP_DB)  # atomic — no half-written DB on a crashed start
    if os.path.exists(_TMP_DB):
        os.environ["EDUPATH_DB_PATH"] = _TMP_DB
