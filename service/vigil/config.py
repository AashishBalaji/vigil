from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    postgres_dsn: str
    mongo_uri: str
    mongo_db_name: str
    model_path: str
    # "real" uses a genuine pymongo client; "mock" uses mongomock, with
    # the identical pymongo-shaped API, for local/offline development
    # where no mongod is available. CI always runs against a real
    # mongo service container -- see .github/workflows/ci.yml.
    mongo_backend: str

    @staticmethod
    def from_env() -> "Settings":
        return Settings(
            postgres_dsn=os.environ.get(
                "VIGIL_POSTGRES_DSN",
                "postgresql://postgres:postgres@localhost:5432/vigil",
            ),
            mongo_uri=os.environ.get("VIGIL_MONGO_URI", "mongodb://localhost:27017"),
            mongo_db_name=os.environ.get("VIGIL_MONGO_DB", "vigil"),
            model_path=os.environ.get(
                "VIGIL_MODEL_PATH",
                os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "model", "artifacts", "model.joblib"),
            ),
            mongo_backend=os.environ.get("VIGIL_MONGO_BACKEND", "real"),
        )


settings = Settings.from_env()
