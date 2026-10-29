from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from vigil.db import mongo, postgres
from vigil.routers.alerts import router as alerts_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    postgres.init_schema()
    yield


app = FastAPI(title="Vigil — Explainable AML Alert Triage", lifespan=lifespan)

# The dashboard is a plain static HTML/CSS/JS page served from a
# different origin during local development (file:// or a simple
# static server); CORS is wide open here deliberately, same caveat as
# any demo project -- a real deployment would scope this to the
# dashboard's actual origin.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(alerts_router)


@app.get("/health")
def health():
    """
    Checks both backing stores are actually reachable, not just that
    the process is up -- a bare "process alive" health check would
    have reported healthy right through failure mode #3 in
    RUNBOOK.md (a dependency outage that ingestion fails loudly on,
    but that this endpoint alone would have stayed silent about).
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
