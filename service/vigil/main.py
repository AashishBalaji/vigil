from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from vigil.auth import seed_demo_users
from vigil.config import settings
from vigil.db import mongo, postgres
from vigil.routers.alerts import router as alerts_router
from vigil.routers.auth import router as auth_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    postgres.init_schema()
    seed_demo_users()
    yield


app = FastAPI(title="Vigil — Explainable AML Alert Triage", lifespan=lifespan)

# Scoped to the dashboard's actual origin(s), read from
# VIGIL_CORS_ORIGINS (see config.py for the defaults this project
# actually serves the dashboard from). An earlier version of this
# file used allow_origins=["*"] as a local-dev shortcut -- that's a
# real gap for anything that will ever run outside a laptop, not a
# cosmetic caveat, so it's fixed rather than just documented.
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(alerts_router)


@app.get("/health")
def health():
    """
    Checks both backing stores are actually reachable, not just that
    the process is up -- a bare "process alive" health check would
    have reported healthy right through failure mode #3 in
    RUNBOOK.md (a dependency outage that ingestion fails loudly on,
    but that this endpoint alone would have stayed silent about).
    Deliberately not behind auth -- a monitoring probe shouldn't need
    a bearer token to ask "are you up".
    """
    checks = {"postgres": "ok", "mongo": "ok"}
    try:
        with postgres.cursor() as cur:
            cur.execute("SELECT 1")
    except Exception as exc:
        checks["postgres"] = f"error: {exc}"

    try:
        mongo.get_evidence(-1)  # a lookup that touches the connection without assuming any data exists
    except Exception as exc:
        checks["mongo"] = f"error: {exc}"

    overall = "ok" if all(v == "ok" for v in checks.values()) else "degraded"
    return {"status": overall, "checks": checks}
