"""
Sets test-safe environment variables before anything in `vigil` is
imported. The model path and mongo backend matter most: a real
trained model artifact is used (not a stub) so scoring/explanation
tests exercise the genuine SHAP pipeline, and mongomock is the
*default* so the suite runs offline without a real mongod -- CI
overrides VIGIL_MONGO_BACKEND=real to point at an actual mongo service
container instead (see .github/workflows/ci.yml), so the mongomock
path is a documented local-dev convenience, not a substitute for the
real integration test.
"""

import os

import pytest

os.environ.setdefault(
    "VIGIL_POSTGRES_DSN", "postgresql://postgres:postgres@localhost:5432/vigil_test"
)
os.environ.setdefault("VIGIL_MONGO_BACKEND", "mock")
os.environ.setdefault(
    "VIGIL_MODEL_PATH",
    os.path.join(os.path.dirname(__file__), "..", "..", "model", "artifacts", "model.joblib"),
)

from vigil.db import mongo, postgres  # noqa: E402


@pytest.fixture(autouse=True)
def clean_state():
    postgres.init_schema()
    with postgres.cursor() as cur:
        cur.execute("TRUNCATE dispositions, alerts RESTART IDENTITY")
    # Must actually delete Mongo's documents, not just reset the
    # client object -- see the comment on clear_all_evidence() for
    # why the two are not the same thing against a real mongod.
    mongo.clear_all_evidence()
    yield
