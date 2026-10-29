from vigil.features import AlertFeatures
from vigil.scoring import score_alert

_STRUCTURING_TP_PROFILE = AlertFeatures(
    txn_count_30d=18,
    total_amount_30d=95_000,
    max_single_txn=9_200,
    distinct_counterparties_30d=3,
    pct_round_amounts=0.2,
    pct_just_under_threshold=0.8,
    jurisdiction_risk_score=0.3,
    days_since_last_activity=2,
    velocity_score=4.5,
    prior_sars_count=0,
    account_age_days=900,
)

_BENIGN_PROFILE = AlertFeatures(
    txn_count_30d=2,
    total_amount_30d=3_000,
    max_single_txn=1_500,
    distinct_counterparties_30d=1,
    pct_round_amounts=0.1,
    pct_just_under_threshold=0.0,
    jurisdiction_risk_score=0.05,
    days_since_last_activity=10,
    velocity_score=0.5,
    prior_sars_count=0,
    account_age_days=2500,
)


def test_score_is_a_valid_probability():
    score, _ = score_alert(_STRUCTURING_TP_PROFILE)
    assert 0.0 <= score <= 1.0


def test_a_clear_structuring_profile_scores_higher_than_a_benign_one():
    tp_score, _ = score_alert(_STRUCTURING_TP_PROFILE)
    benign_score, _ = score_alert(_BENIGN_PROFILE)
    assert tp_score > benign_score


def test_explanation_covers_every_feature_and_is_sorted_by_magnitude():
    _, explanation = score_alert(_STRUCTURING_TP_PROFILE)
    assert {e["feature"] for e in explanation} == set(AlertFeatures.model_fields.keys())
    magnitudes = [abs(e["contribution"]) for e in explanation]
    assert magnitudes == sorted(magnitudes, reverse=True)


def test_scoring_is_deterministic():
    score1, explanation1 = score_alert(_STRUCTURING_TP_PROFILE)
    score2, explanation2 = score_alert(_STRUCTURING_TP_PROFILE)
    assert score1 == score2
    assert explanation1 == explanation2
