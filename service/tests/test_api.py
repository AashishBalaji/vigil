from concurrent.futures import ThreadPoolExecutor

from fastapi.testclient import TestClient

from vigil.main import app

client = TestClient(app)

_FEATURES = {
    "txn_count_30d": 18,
    "total_amount_30d": 95000,
    "max_single_txn": 9200,
    "distinct_counterparties_30d": 3,
    "pct_round_amounts": 0.2,
    "pct_just_under_threshold": 0.8,
    "jurisdiction_risk_score": 0.3,
    "days_since_last_activity": 2,
    "velocity_score": 4.5,
    "prior_sars_count": 0,
    "account_age_days": 900,
}


def _ingest(headers, customer_id="CUST-000001", typology="structuring"):
    resp = client.post(
        "/alerts",
        json={"customer_id": customer_id, "typology_hint": typology, "features": _FEATURES},
        headers=headers,
    )
    assert resp.status_code == 201
    return resp.json()


def test_health_does_not_require_auth():
    resp = client.get("/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["checks"] == {"postgres": "ok", "mongo": "ok"}


def test_alerts_endpoints_reject_an_unauthenticated_caller():
    assert client.get("/alerts").status_code == 401
    assert client.post("/alerts", json={}).status_code == 401


def test_login_rejects_wrong_password():
    resp = client.post("/auth/login", data={"username": "analyst1", "password": "wrong"})
    assert resp.status_code == 401


def test_login_rejects_unknown_user():
    resp = client.post("/auth/login", data={"username": "nobody", "password": "x"})
    assert resp.status_code == 401


def test_full_lifecycle_ingest_queue_detail_disposition(auth_headers):
    alert = _ingest(auth_headers)
    alert_id = alert["id"]
    assert alert["status"] == "OPEN"
    assert 0.0 <= alert["score"] <= 1.0

    queue = client.get("/alerts", params={"status": "OPEN"}, headers=auth_headers).json()
    assert any(a["id"] == alert_id for a in queue)

    detail = client.get(f"/alerts/{alert_id}", headers=auth_headers).json()
    assert detail["explanation"]
    assert detail["raw_features"]["txn_count_30d"] == 18

    disposition = client.post(
        f"/alerts/{alert_id}/disposition",
        json={"decision": "TRUE_POSITIVE", "rationale": "clear structuring pattern"},
        headers=auth_headers,
    )
    assert disposition.status_code == 201
    body = disposition.json()
    assert body["decision"] == "TRUE_POSITIVE"
    # The analyst identity comes from the authenticated token now, not
    # a free-text field the caller could have set to anything.
    assert body["analyst"] == "analyst1"

    queue_after = client.get("/alerts", params={"status": "OPEN"}, headers=auth_headers).json()
    assert all(a["id"] != alert_id for a in queue_after)


def test_404_for_a_nonexistent_alert(auth_headers):
    assert client.get("/alerts/999999", headers=auth_headers).status_code == 404
    resp = client.post(
        "/alerts/999999/disposition",
        json={"decision": "TRUE_POSITIVE", "rationale": "x"},
        headers=auth_headers,
    )
    assert resp.status_code == 404


def test_an_already_decided_alert_cannot_be_redecided(auth_headers):
    alert = _ingest(auth_headers)
    alert_id = alert["id"]
    first = client.post(
        f"/alerts/{alert_id}/disposition",
        json={"decision": "FALSE_POSITIVE", "rationale": "benign pattern"},
        headers=auth_headers,
    )
    assert first.status_code == 201

    second = client.post(
        f"/alerts/{alert_id}/disposition",
        json={"decision": "TRUE_POSITIVE", "rationale": "changed my mind"},
        headers=auth_headers,
    )
    assert second.status_code == 409


def test_concurrent_dispositions_on_the_same_alert_exactly_one_wins(auth_headers):
    """
    Mirrors the concurrency-correctness discipline used elsewhere in
    this portfolio: fire genuinely concurrent disposition attempts at
    the same OPEN alert via a thread pool (not sequential calls
    dressed up as a race test) and assert exactly one succeeds. The
    guarantee comes from record_disposition's single conditional
    UPDATE ... WHERE status = 'OPEN', not from anything in this test
    -- and now also exercises the connection pool under genuine
    concurrent load (pool max is 20, comfortably above these 10).
    """
    alert = _ingest(auth_headers)
    alert_id = alert["id"]

    def attempt(_i: int):
        return client.post(
            f"/alerts/{alert_id}/disposition",
            json={"decision": "TRUE_POSITIVE", "rationale": "race"},
            headers=auth_headers,
        )

    with ThreadPoolExecutor(max_workers=10) as pool:
        results = list(pool.map(attempt, range(10)))

    statuses = [r.status_code for r in results]
    assert statuses.count(201) == 1
    assert statuses.count(409) == 9
