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


def reset_client_cache() -> None:
    """Test-only: forces a fresh client on the next call (new mongomock instance per test)."""
    _client.cache_clear()
