from __future__ import annotations

from functools import lru_cache
from typing import Any

import joblib
import pandas as pd
import shap

from vigil.config import settings
from vigil.features import FEATURE_NAMES, AlertFeatures


@lru_cache(maxsize=1)
def _model():
    return joblib.load(settings.model_path)


@lru_cache(maxsize=1)
def _explainer():
    # TreeExplainer computes exact Shapley values for tree ensembles
    # directly from the tree structure -- no background/reference
    # dataset needed, unlike KernelExplainer. This is the reason the
    # training script was built around a classic sklearn
    # GradientBoostingClassifier rather than a more exotic model: a
    # tree-based model is the one architecture where "exact, fast,
    # per-prediction feature attribution" and "strong tabular
    # performance" aren't in tension.
    return shap.TreeExplainer(_model())


def score_alert(features: AlertFeatures) -> tuple[float, list[dict[str, Any]]]:
    """
    Returns (priority_score, explanation). priority_score is
    P(true_positive) in [0, 1]. explanation is the per-feature SHAP
    contribution to that score, sorted by absolute magnitude -- the
    piece that makes this an AML tool an analyst (and a regulator)
    could actually trust, rather than a bare number.
    """
    # A DataFrame with the exact column names/order the model was
    # trained on -- not a bare array -- so sklearn's own
    # feature-name-mismatch check actually protects us if
    # FEATURE_NAMES and the trained model's column order ever drift
    # apart, instead of that check being silenced by position-only
    # input.
    vector = pd.DataFrame([features.to_vector()], columns=FEATURE_NAMES)
    model = _model()
    score = float(model.predict_proba(vector)[0, 1])

    explainer = _explainer()
    shap_values = explainer.shap_values(vector)
    # shap_values shape for a binary GradientBoostingClassifier via
    # TreeExplainer is (1, n_features) for the positive class log-odds
    # contribution; handle both that and the (n_classes,) list form
    # defensively since shap's return shape has changed across
    # versions.
    if isinstance(shap_values, list):
        row = shap_values[1][0] if len(shap_values) > 1 else shap_values[0][0]
    else:
        row = shap_values[0]

    contributions = [
        {"feature": name, "value": float(getattr(features, name)), "contribution": float(contrib)}
        for name, contrib in zip(FEATURE_NAMES, row)
    ]
    contributions.sort(key=lambda c: abs(c["contribution"]), reverse=True)
    return score, contributions
