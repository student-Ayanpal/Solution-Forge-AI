"""
FastAPI application entry point.

Any of these work (from the repo root):

    uvicorn backend.main:app --reload     # preferred
    python -m backend.main                # equivalent
    python backend/main.py                # convenient when double-clicking
    cd backend && python main.py

Wires all route modules together and exposes a /health endpoint
so we can verify DB connectivity easily.
"""

import os
import sys

# Every module here uses absolute `backend.*` imports, which only resolve when
# the *repo root* is on sys.path. uvicorn adds the CWD for us, but running this
# file directly (`python backend/main.py`, or `python main.py` from inside
# backend/) puts backend/ on sys.path instead and fails with
# "ModuleNotFoundError: No module named 'backend'". Deriving the root from
# __file__ makes every entry point above work regardless of CWD.
_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from fastapi import FastAPI
from backend.db.database import db
from backend.routers import auth, consultations

app = FastAPI(
    title="SolutionForgeAI API",
    description="Multi-agent AI solution consulting backend.",
    version="0.2.0",
)

app.include_router(auth.router)
app.include_router(consultations.router)



@app.get("/health")
def health_check():
    """Quick check that the API + MongoDB are reachable."""
    db.command("ping")
    return {"status": "ok", "database": "connected"}


if __name__ == "__main__":
    import uvicorn

    # `reload=True` re-executes this file in a subprocess, so the sys.path
    # bootstrap above runs again there — the import string resolves fine.
    uvicorn.run("backend.main:app", host="0.0.0.0", port=8000, reload=True)
