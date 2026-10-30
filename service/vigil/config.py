from __future__ import annotations

import os
from dataclasses import dataclass, field


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
    # Postgres connection pool bounds. A pool, not a fresh connect/
    # close per request -- the concurrency test alone fires 10
    # simultaneous disposition attempts, and a real deployment's
    # request volume only makes a per-request connection more
    # wasteful, not less.
    postgres_pool_min: int
    postgres_pool_max: int
    # The dashboard's own origin(s), comma-separated. Defaults to the
    # two ways this project is actually served locally (a plain
    # `python -m http.server` on 8011, matching CI's ui-e2e job, and
    # VS Code's Live Server default on 5500) -- never "*". A real
    # deployment sets VIGIL_CORS_ORIGINS to the dashboard's real host.
    cors_origins: list[str] = field(default_factory=list)
    jwt_secret: str = ""
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60

    @staticmethod
    def from_env() -> "Settings":
        cors_env = os.environ.get("VIGIL_CORS_ORIGINS", "http://localhost:8011,http://localhost:5500,http://127.0.0.1:8011")
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
            postgres_pool_min=int(os.environ.get("VIGIL_PG_POOL_MIN", "2")),
            postgres_pool_max=int(os.environ.get("VIGIL_PG_POOL_MAX", "20")),
            cors_origins=[o.strip() for o in cors_env.split(",") if o.strip()],
            jwt_secret=os.environ.get("VIGIL_JWT_SECRET", "dev-only-insecure-secret-change-me"),
            jwt_algorithm=os.environ.get("VIGIL_JWT_ALGORITHM", "HS256"),
            access_token_expire_minutes=int(os.environ.get("VIGIL_ACCESS_TOKEN_EXPIRE_MINUTES", "60")),
        )


settings = Settings.from_env()
