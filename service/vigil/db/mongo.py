from __future__ import annotations

from functools import lru_cache
from typing import Any

from vigil.config import settings


@lru_cache(maxsize=1)
def _client():
    """
    Returns a pymongo-API-compatible client. "real" talks to an actual
    mongod (CI's service container, or a real local one); "mock" uses
    mongomock, which implements the same collection/find/insert_one
    surface, so evidence.py's code is identical either way -- only
    this one factory function knows which backend is live.
    """
    if settings.mongo_backend == "mock":
        import mongomock

        return mongomock.MongoClient()
    import pymongo

    return pymongo.MongoClient(settings.mongo_uri, serverSelectionTimeoutMS=5000)


def _evidence_collection():
    return _client()[settings.mongo_db_name]["alert_evidence"]


def store_evidence(alert_id: int, typology_hint: str, raw_features: dict[str, Any], explanation: list[dict[str, Any]]) -> None:
    _evidence_collection().insert_one(
        {
            "_id": alert_id,
            "typology_hint": typology_hint,
            "raw_features": raw_features,
            "explanation": explanation,
        }
    )


def get_evidence(alert_id: int) -> dict[str, Any] | None:
    return _evidence_collection().find_one({"_id": alert_id})


def clear_all_evidence() -> None:
    """
    Test-only. An earlier version of this file instead exposed
    `reset_client_cache()`, which just cleared the lru_cache so the
    *next* call built a fresh client object -- that happened to also
    wipe all data when the backend was mongomock, because a new
    mongomock.MongoClient() is a fresh in-memory database. Against a
    real mongod, a new MongoClient() reconnects to the *same*
    persistent data, so nothing was actually cleared -- and Postgres's
    `TRUNCATE ... RESTART IDENTITY` between tests means alert IDs
    restart at 1 every test, so the second test to ingest an alert
    collided on `_id: 1` with a document the first test had already
    left behind: `DuplicateKeyError`, caught by CI's real-Mongo job,
    never visible locally where mongomock was masking it. This
    function does the thing that was actually needed instead:
    deletes every document, identically regardless of which backend
    is live.
    """
    _evidence_collection().delete_many({})
