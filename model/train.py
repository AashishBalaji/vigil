"""
Trains the AML triage classifier and reports metrics honestly,
including the one that actually matters operationally: at a recall
level an AML team would actually accept, how much does the analyst
queue shrink?

A GradientBoostingClassifier (not a more exotic architecture) is the
deliberate choice -- shap.TreeExplainer computes exact, fast Shapley
values directly from the tree structure for this model family, which
is the thing that makes scoring.py's explanation layer real rather
than approximated.
"""

from __future__ import annotations

import json
import os
import sys

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import GradientBoostingClassifier
from sklearn.metrics import average_precision_score, precision_recall_curve, roc_auc_score
from sklearn.model_selection import train_test_split

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "service"))
from vigil.features import FEATURE_NAMES  # noqa: E402

ARTIFACTS_DIR = os.path.join(os.path.dirname(__file__), "artifacts")
TARGET_RECALL = 0.90


def _volume_reduction_at_recall(y_true: np.ndarray, scores: np.ndarray, target_recall: float) -> dict:
    """
    The operational KPI an AML triage team actually tracks: pick the
    lowest score threshold that still catches >= target_recall of true
    positives, then report what fraction of the queue falls *below*
    that threshold -- i.e., how much of the analyst workload the model
    would let the team safely deprioritize without missing the recall
    target. This is reported on held-out test data, not training data.
    """
    precision, recall, thresholds = precision_recall_curve(y_true, scores)
    # precision_recall_curve returns recall in descending order aligned
    # with ascending thresholds; thresholds has one fewer element.
    usable = recall[:-1] >= target_recall
    if not usable.any():
        return {"achievable": False, "target_recall": target_recall}
    # Among thresholds achieving the target recall, the highest
    # threshold gives the most volume reduction.
    best_idx = np.argmax(np.where(usable, thresholds, -np.inf))
    threshold = float(thresholds[best_idx])
    flagged = scores >= threshold
    achieved_recall = float((flagged & (y_true == 1)).sum() / max((y_true == 1).sum(), 1))
    volume_reduction = float(1.0 - flagged.mean())
    return {
        "achievable": True,
        "target_recall": target_recall,
        "achieved_recall": round(achieved_recall, 4),
        "threshold": round(threshold, 4),
        "queue_volume_reduction": round(volume_reduction, 4),
    }


def main() -> None:
    data_path = os.path.join(ARTIFACTS_DIR, "alerts_dataset.csv")
    if not os.path.exists(data_path):
        raise SystemExit("Run generate_data.py first to produce alerts_dataset.csv")

    df = pd.read_csv(data_path)
    X = df[FEATURE_NAMES]
    y = df["is_true_positive"]

    X_train, X_temp, y_train, y_temp = train_test_split(X, y, test_size=0.4, stratify=y, random_state=42)
    X_val, X_test, y_val, y_test = train_test_split(X_temp, y_temp, test_size=0.5, stratify=y_temp, random_state=42)

    model = GradientBoostingClassifier(
        n_estimators=150,
        max_depth=3,
        learning_rate=0.08,
        subsample=0.8,
        random_state=42,
    )
    model.fit(X_train, y_train)

    val_scores = model.predict_proba(X_val)[:, 1]
    test_scores = model.predict_proba(X_test)[:, 1]

    metrics = {
        "n_train": len(X_train),
        "n_val": len(X_val),
        "n_test": len(X_test),
        "test_roc_auc": round(float(roc_auc_score(y_test, test_scores)), 4),
        "test_average_precision": round(float(average_precision_score(y_test, test_scores)), 4),
        "val_volume_reduction_at_target_recall": _volume_reduction_at_recall(y_val.to_numpy(), val_scores, TARGET_RECALL),
        "test_volume_reduction_at_target_recall": _volume_reduction_at_recall(y_test.to_numpy(), test_scores, TARGET_RECALL),
    }

    os.makedirs(ARTIFACTS_DIR, exist_ok=True)
    joblib.dump(model, os.path.join(ARTIFACTS_DIR, "model.joblib"))
    with open(os.path.join(ARTIFACTS_DIR, "metrics.json"), "w") as f:
        json.dump(metrics, f, indent=2)

    print(json.dumps(metrics, indent=2))


if __name__ == "__main__":
    main()
