from __future__ import annotations

from typing import Literal

from pydantic import BaseModel

from vigil.features import AlertFeatures


class AlertIn(BaseModel):
    customer_id: str
    typology_hint: str
    features: AlertFeatures


class ExplanationItem(BaseModel):
    feature: str
    value: float
    contribution: float


class AlertOut(BaseModel):
    id: int
    customer_id: str
    typology_hint: str
    score: float
    status: str
    created_at: str
    decided_at: str | None = None


class AlertDetailOut(AlertOut):
    explanation: list[ExplanationItem]
    raw_features: dict


class DispositionIn(BaseModel):
    decision: Literal["TRUE_POSITIVE", "FALSE_POSITIVE", "ESCALATED"]
    rationale: str
    analyst: str


class DispositionOut(BaseModel):
    id: int
    alert_id: int
    decision: str
    rationale: str
    analyst: str
    decided_at: str
