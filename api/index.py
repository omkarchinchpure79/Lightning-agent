"""
index.py — Vercel serverless entrypoint for the EduPath API (see vercel.json).

The cold-start DB seed/unpack itself lives in api/_seed_runtime.py, imported
first thing by api.main — this module just needs repo root on sys.path (for
the `import engine_adapter` sys.path trick app/engine_adapter.py relies on)
and to re-export the FastAPI app.
"""
import os
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from api.main import app  # noqa: E402
