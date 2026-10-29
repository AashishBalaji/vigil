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


def _ingest(customer_id="CUST-000001", typology="structuring"):
    resp = client.post(
        "/alerts",
        json={"customer_id": customer_id, "typology_hint": typology, "features": _FEATURES},
    )
    assert resp.status_code == 201
    return resp.json()


def test_health():
    resp = client.get("/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["checks"] == {"postgres": "ok", "mongo": "ok"}


def test_full_lifecycle_ingest_queue_detail_disposition():
    alert = _ingest()
    alert_id = alert["id"]
    assert alert["status"] == "OPEN"
    assert 0.0 <= alert["score"] <= 1.0

    queue = client.get("/alerts", params={"status": "OPEN"}).json()
    assert any(a["id"] == alert_id for a in queue)

    detail = client.get(f"/alerts/{alert_id}").json()
    assert detail["explanation"]
    assert detail["raw_features"]["txn_count_30d"] == 18

    disposition = client.post(
        f"/alerts/{alert_id}/disposition",
        json={"decision": "TRUE_POSITIVE", "rationale": "clear structuring pattern", "analyst": "a.reviewer"},
    )
    assert disposition.status_code == 201
    assert disposition.json()["decision"] == "TRUE_POSITIVE"

    queue_after = client.get("/alerts", params={"status": "OPEN"}).json()
    assert all(a["id"] != alert_id for a in queue_after)


def test_404_for_a_nonexistent_alert():
    assert client.get("/alerts/999999").status_code == 404
    resp = client.post(
        "/alerts/999999/disposition",
        json={"decision": "TRUE_POSITIVE", "rationale": "x", "analyst": "a"},
    )
    assert resp.status_code == 404


def test_an_already_decided_alert_cannot_be_redecided():
    alert = _ingest()
    alert_id = alert["id"]
    first = client.post(
        f"/alerts/{alert_id}/disposition",
        json={"decision": "FALSE_POSITIVE", "rationale": "benign pattern", "analyst": "a.reviewer"},
    )
    assert first.status_code == 201

    second = client.post(
        f"/alerts/{alert_id}/disposition",
        json={"decision": "TRUE_POSITIVE", "rationale": "changed my mind", "analyst": "b.reviewer"},
    )
    assert second.status_code == 409


def test_concurrent_dispositions_on_the_same_alert_exactly_one_wins():
    """
    Mirrors the concurrency-correctness discipline used elsewhere in
    this portfolio: fire genuinely concurrent disposition attempts at
    the same OPEN alert via a thread pool (not sequential calls
    dressed up as a race test) and assert exactly one succeeds. The
    guarantee comes from record_disposition's single conditional
    UPDATE ... WHERE status = 'OPEN', not from anything in this test.
    """
    alert = _ingest()
    alert_id = alert["id"]

    def attempt(analyst: str):
        return client.post(
            f"/alerts/{alert_id}/disposition",
            json={"decision": "TRUE_POSITIVE", "rationale": "race", "analyst": analyst},
        )

    with ThreadPoolExecutor(max_workers=10) as pool:
        results = list(pool.map(attempt, [f"analyst-{i}" for i in range(10)]))

    statuses = [r.status_code for r in results]
    assert statuses.count(201) == 1
    assert statuses.count(409) == 9
