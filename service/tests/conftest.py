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
os.environ.setdefault("VIGIL_JWT_SECRET", "test-only-secret")

from vigil.auth import seed_demo_users  # noqa: E402
from vigil.db import mongo, postgres  # noqa: E402


@pytest.fixture(autouse=True)
def clean_state():
    postgres.init_schema()
    with postgres.cursor() as cur:
        cur.execute("TRUNCATE dispositions, alerts RESTART IDENTITY")
    # Users are seeded idempotently (ON CONFLICT DO NOTHING in
    # create_user), not truncated -- the demo accounts' identities
    # should persist across tests the same way they would across
    # restarts of the real service.
    seed_demo_users()
    # Must actually delete Mongo's documents, not just reset the
    # client object -- see the comment on clear_all_evidence() for
    # why the two are not the same thing against a real mongod.
    mongo.clear_all_evidence()
    yield


@pytest.fixture
def auth_headers():
    """
    Logs in as the demo analyst account and returns a ready-to-use
    Authorization header, so every test that needs an authenticated
    call does one `client.post(..., headers=auth_headers)` rather than
    hand-rolling a login each time.
    """
    from fastapi.testclient import TestClient

    from vigil.main import app

    client = TestClient(app)
    resp = client.post("/auth/login", data={"username": "analyst1", "password": "analyst1-pass"})
    assert resp.status_code == 200, resp.text
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}
