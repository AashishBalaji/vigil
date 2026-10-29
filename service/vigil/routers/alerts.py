from __future__ import annotations

from fastapi import APIRouter, HTTPException

from vigil.db import mongo, postgres
from vigil.schemas import AlertDetailOut, AlertIn, AlertOut, DispositionIn, DispositionOut
from vigil.scoring import score_alert

router = APIRouter()


def _serialize_alert(row: dict) -> dict:
    return {
        "id": row["id"],
        "customer_id": row["customer_id"],
        "typology_hint": row["typology_hint"],
        "score": row["score"],
        "status": row["status"],
        "created_at": row["created_at"].isoformat(),
        "decided_at": row["decided_at"].isoformat() if row.get("decided_at") else None,
    }


@router.post("/alerts", response_model=AlertOut, status_code=201)
def ingest_alert(alert: AlertIn):
    score, explanation = score_alert(alert.features)
    alert_id = postgres.insert_alert(alert.customer_id, alert.typology_hint, score)
    mongo.store_evidence(
        alert_id=alert_id,
        typology_hint=alert.typology_hint,
        raw_features=alert.features.model_dump(),
        explanation=explanation,
    )
    row = postgres.get_alert(alert_id)
    return _serialize_alert(row)


@router.get("/alerts", response_model=list[AlertOut])
def list_queue(status: str = "OPEN", limit: int = 100):
    rows = postgres.list_queue(status=status, limit=limit)
    return [_serialize_alert(r) for r in rows]


@router.get("/alerts/{alert_id}", response_model=AlertDetailOut)
def get_alert_detail(alert_id: int):
    row = postgres.get_alert(alert_id)
    if row is None:
        raise HTTPException(status_code=404, detail="alert not found")
    evidence = mongo.get_evidence(alert_id)
    if evidence is None:
        raise HTTPException(status_code=500, detail="alert exists in Postgres but its evidence is missing in Mongo")
    base = _serialize_alert(row)
    base["explanation"] = evidence["explanation"]
    base["raw_features"] = evidence["raw_features"]
    return base


@router.post("/alerts/{alert_id}/disposition", response_model=DispositionOut, status_code=201)
def record_disposition(alert_id: int, disposition: DispositionIn):
    row = postgres.get_alert(alert_id)
    if row is None:
        raise HTTPException(status_code=404, detail="alert not found")
    try:
        created = postgres.record_disposition(
            alert_id=alert_id,
            decision=disposition.decision,
            rationale=disposition.rationale,
            analyst=disposition.analyst,
        )
    except postgres.AlreadyDecidedError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    created["decided_at"] = created["decided_at"].isoformat()
    return created
