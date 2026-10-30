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
    # No `analyst` field here anymore -- it used to be free text the
    # caller supplied, which meant anyone could record a decision
    # under any name. The analyst identity now comes from the
    # authenticated bearer token (see routers/alerts.py), not the
    # request body.
    decision: Literal["TRUE_POSITIVE", "FALSE_POSITIVE", "ESCALATED"]
    rationale: str


class DispositionOut(BaseModel):
    id: int
    alert_id: int
    decision: str
    rationale: str
    analyst: str
    decided_at: str


class TokenOut(BaseModel):
    access_token: str
    token_type: str
    role: str
