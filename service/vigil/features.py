"""
The single source of truth for what an AML alert's feature vector looks
like. The synthetic data generator and the training script both import
FEATURE_NAMES from here (rather than hardcoding their own column list)
so the dataset a model is trained on and the feature vector the live
service builds at inference time can never silently drift apart --
a real and common source of "the model that worked in training is
garbage in production" bugs.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

# Order matters: this is the exact column order the model was trained
# on and the exact order scoring.py builds its feature vector in.
FEATURE_NAMES: list[str] = [
    "txn_count_30d",
    "total_amount_30d",
    "max_single_txn",
    "distinct_counterparties_30d",
    "pct_round_amounts",
    "pct_just_under_threshold",
    "jurisdiction_risk_score",
    "days_since_last_activity",
    "velocity_score",
    "prior_sars_count",
    "account_age_days",
]


class AlertFeatures(BaseModel):
    """
    The feature payload a monitoring rule hands to Vigil when it raises
    an alert. In a real deployment this would be computed upstream by
    the transaction-monitoring system; here the synthetic generator
    plays that role, honestly documented as such.
    """

    txn_count_30d: int = Field(..., ge=0, description="Number of transactions in the trailing 30 days")
    total_amount_30d: float = Field(..., ge=0, description="Total transacted amount in the trailing 30 days")
    max_single_txn: float = Field(..., ge=0, description="Largest single transaction in the window")
    distinct_counterparties_30d: int = Field(..., ge=0, description="Distinct counterparties transacted with")
    pct_round_amounts: float = Field(..., ge=0, le=1, description="Fraction of transactions that are round-number amounts")
    pct_just_under_threshold: float = Field(
        ..., ge=0, le=1, description="Fraction of transactions just under the $10k CTR-style reporting threshold"
    )
    jurisdiction_risk_score: float = Field(..., ge=0, le=1, description="Counterparty-jurisdiction risk score")
    days_since_last_activity: int = Field(..., ge=0, description="Days of dormancy before this activity burst")
    velocity_score: float = Field(..., ge=0, description="Rate-of-change in transaction velocity vs. the account's own baseline")
    prior_sars_count: int = Field(..., ge=0, description="Prior Suspicious Activity Reports filed on this customer")
    account_age_days: int = Field(..., ge=0, description="Account age in days")

    def to_vector(self) -> list[float]:
        return [float(getattr(self, name)) for name in FEATURE_NAMES]
