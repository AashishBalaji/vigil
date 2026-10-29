"""
Synthetic AML alert generator.

Real AML alert data is regulated and private -- there is no legitimate
way to use real bank data for a portfolio project, and this file says
so plainly rather than letting the dataset's realism imply otherwise.

What this generates instead: for each of four AML typologies, a
monitoring rule that fires on a shared, naive threshold-based
condition -- which is how real transaction-monitoring systems actually
work, and why they're so noisy -- plus two underlying generative
profiles per typology: a genuine bad-actor pattern (true positive) and
a benign pattern that happens to trip the same naive rule (false
positive). Real AML alert systems run at roughly 90-98% false-positive
rates; this generator is deliberately a little less lopsided than that
(it would make for a trivial, uninteresting modeling problem and an
uninformative explanation layer) while keeping the same qualitative
shape: most alerts are noise, and separating the two requires looking
at more than the one feature the rule itself fired on.
"""

from __future__ import annotations

import json
import os
import sys
from dataclasses import dataclass

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "service"))
from vigil.features import FEATURE_NAMES  # noqa: E402

RNG_SEED = 42
ARTIFACTS_DIR = os.path.join(os.path.dirname(__file__), "artifacts")


@dataclass
class Typology:
    name: str
    # Probability an alert of this typology is a genuine true positive.
    true_positive_rate: float
    # Feature generators: callables (rng, n) -> np.ndarray, one profile
    # for true positives and one for the benign-but-rule-tripping case.
    tp_profile: dict
    fp_profile: dict


def _normal(mean: float, std: float, low: float = 0.0, high: float | None = None):
    def gen(rng: np.random.Generator, n: int) -> np.ndarray:
        vals = rng.normal(mean, std, n)
        vals = np.clip(vals, low, high if high is not None else np.inf)
        return vals

    return gen


def _beta_scaled(a: float, b: float):
    def gen(rng: np.random.Generator, n: int) -> np.ndarray:
        return rng.beta(a, b, n)

    return gen


def _poisson(lam: float):
    def gen(rng: np.random.Generator, n: int) -> np.ndarray:
        return rng.poisson(lam, n).astype(float)

    return gen


TYPOLOGIES = [
    Typology(
        name="structuring",
        true_positive_rate=0.22,
        tp_profile={
            "txn_count_30d": _poisson(18),
            "total_amount_30d": _normal(95_000, 20_000, low=20_000),
            "max_single_txn": _normal(9_200, 400, low=5_000, high=9_999),
            "distinct_counterparties_30d": _poisson(3),
            "pct_round_amounts": _beta_scaled(2, 6),
            "pct_just_under_threshold": _beta_scaled(8, 2),
            "jurisdiction_risk_score": _beta_scaled(2, 5),
            "days_since_last_activity": _poisson(2),
            "velocity_score": _normal(4.5, 1.2, low=0),
            "prior_sars_count": _poisson(0.3),
            "account_age_days": _normal(900, 400, low=30),
        },
        fp_profile={
            # A small business making frequent near-threshold cash
            # deposits for entirely mundane reasons (daily till
            # deposits) -- trips the same "lots of just-under-10k
            # transactions" rule with no structuring intent.
            "txn_count_30d": _poisson(16),
            "total_amount_30d": _normal(80_000, 15_000, low=20_000),
            "max_single_txn": _normal(8_800, 600, low=5_000, high=9_999),
            "distinct_counterparties_30d": _poisson(2),
            "pct_round_amounts": _beta_scaled(5, 3),
            "pct_just_under_threshold": _beta_scaled(7, 3),
            "jurisdiction_risk_score": _beta_scaled(1.5, 8),
            "days_since_last_activity": _poisson(1),
            "velocity_score": _normal(1.2, 0.5, low=0),
            "prior_sars_count": _poisson(0.02),
            "account_age_days": _normal(1800, 700, low=60),
        },
    ),
    Typology(
        name="rapid_movement",
        true_positive_rate=0.18,
        tp_profile={
            "txn_count_30d": _poisson(9),
            "total_amount_30d": _normal(260_000, 60_000, low=50_000),
            "max_single_txn": _normal(120_000, 40_000, low=20_000),
            "distinct_counterparties_30d": _poisson(7),
            "pct_round_amounts": _beta_scaled(4, 4),
            "pct_just_under_threshold": _beta_scaled(2, 6),
            "jurisdiction_risk_score": _beta_scaled(3, 4),
            "days_since_last_activity": _poisson(1),
            "velocity_score": _normal(8.0, 2.0, low=0),
            "prior_sars_count": _poisson(0.4),
            "account_age_days": _normal(400, 250, low=10),
        },
        fp_profile={
            # A legitimate payroll or supplier-settlement account that
            # moves a large balance through quickly every pay cycle.
            "txn_count_30d": _poisson(6),
            "total_amount_30d": _normal(220_000, 50_000, low=50_000),
            "max_single_txn": _normal(90_000, 25_000, low=20_000),
            "distinct_counterparties_30d": _poisson(4),
            "pct_round_amounts": _beta_scaled(6, 3),
            "pct_just_under_threshold": _beta_scaled(1.5, 8),
            "jurisdiction_risk_score": _beta_scaled(1.5, 9),
            "days_since_last_activity": _poisson(1),
            "velocity_score": _normal(3.5, 1.0, low=0),
            "prior_sars_count": _poisson(0.01),
            "account_age_days": _normal(1500, 600, low=60),
        },
    ),
    Typology(
        name="high_risk_jurisdiction",
        true_positive_rate=0.15,
        tp_profile={
            "txn_count_30d": _poisson(7),
            "total_amount_30d": _normal(140_000, 40_000, low=20_000),
            "max_single_txn": _normal(60_000, 20_000, low=10_000),
            "distinct_counterparties_30d": _poisson(5),
            "pct_round_amounts": _beta_scaled(5, 3),
            "pct_just_under_threshold": _beta_scaled(3, 5),
            "jurisdiction_risk_score": _beta_scaled(8, 2),
            "days_since_last_activity": _poisson(3),
            "velocity_score": _normal(3.0, 1.0, low=0),
            "prior_sars_count": _poisson(0.5),
            "account_age_days": _normal(500, 300, low=10),
        },
        fp_profile={
            # A customer with ordinary family remittances or trade
            # payments to/from a jurisdiction the risk model flags,
            # with no other suspicious pattern.
            "txn_count_30d": _poisson(5),
            "total_amount_30d": _normal(30_000, 12_000, low=2_000),
            "max_single_txn": _normal(8_000, 3_000, low=1_000),
            "distinct_counterparties_30d": _poisson(2),
            "pct_round_amounts": _beta_scaled(4, 4),
            "pct_just_under_threshold": _beta_scaled(2, 7),
            "jurisdiction_risk_score": _beta_scaled(7, 3),
            "days_since_last_activity": _poisson(5),
            "velocity_score": _normal(1.0, 0.4, low=0),
            "prior_sars_count": _poisson(0.02),
            "account_age_days": _normal(1200, 600, low=60),
        },
    ),
    Typology(
        name="dormant_reactivation",
        true_positive_rate=0.12,
        tp_profile={
            "txn_count_30d": _poisson(10),
            "total_amount_30d": _normal(75_000, 25_000, low=10_000),
            "max_single_txn": _normal(40_000, 15_000, low=5_000),
            "distinct_counterparties_30d": _poisson(4),
            "pct_round_amounts": _beta_scaled(4, 4),
            "pct_just_under_threshold": _beta_scaled(3, 5),
            "jurisdiction_risk_score": _beta_scaled(3, 4),
            "days_since_last_activity": _normal(260, 60, low=120),
            "velocity_score": _normal(6.0, 1.5, low=0),
            "prior_sars_count": _poisson(0.2),
            "account_age_days": _normal(2500, 800, low=200),
        },
        fp_profile={
            # A seasonal or life-event account (inheritance, property
            # sale, a once-a-year business) that is legitimately quiet
            # most of the year and then genuinely active for a stretch.
            "txn_count_30d": _poisson(6),
            "total_amount_30d": _normal(45_000, 18_000, low=5_000),
            "max_single_txn": _normal(25_000, 10_000, low=3_000),
            "distinct_counterparties_30d": _poisson(2),
            "pct_round_amounts": _beta_scaled(5, 4),
            "pct_just_under_threshold": _beta_scaled(2, 7),
            "jurisdiction_risk_score": _beta_scaled(1.5, 8),
            "days_since_last_activity": _normal(200, 50, low=120),
            "velocity_score": _normal(2.0, 0.8, low=0),
            "prior_sars_count": _poisson(0.01),
            "account_age_days": _normal(2200, 700, low=200),
        },
    ),
]


def generate_alerts(n_per_typology: int, seed: int = RNG_SEED) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    frames = []
    for typology in TYPOLOGIES:
        n_tp = rng.binomial(n_per_typology, typology.true_positive_rate)
        n_fp = n_per_typology - n_tp

        tp_rows = {name: typology.tp_profile[name](rng, n_tp) for name in FEATURE_NAMES}
        fp_rows = {name: typology.fp_profile[name](rng, n_fp) for name in FEATURE_NAMES}

        tp_df = pd.DataFrame(tp_rows)
        tp_df["is_true_positive"] = 1
        fp_df = pd.DataFrame(fp_rows)
        fp_df["is_true_positive"] = 0

        combined = pd.concat([tp_df, fp_df], ignore_index=True)
        combined["typology_hint"] = typology.name
        frames.append(combined)

    df = pd.concat(frames, ignore_index=True)

    # Real historical AML disposition labels are themselves imperfect
    # -- "true positive" means an analyst (or a SAR filing) judged it
    # so, not that the underlying ground truth was observed directly.
    # Without some label noise, two cleanly-separated generative
    # profiles make for a trivially separable classification problem
    # and an unrealistically high AUC that wouldn't survive contact
    # with real data. 7% random label flips is a deliberate, documented
    # stand-in for that real-world labeling imperfection.
    flip_mask = rng.random(len(df)) < 0.07
    df.loc[flip_mask, "is_true_positive"] = 1 - df.loc[flip_mask, "is_true_positive"]

    df = df.sample(frac=1.0, random_state=seed).reset_index(drop=True)

    # Integer-valued features should actually be integers, not floats
    # with a .0 -- the generators above use Poisson/clip for realism
    # but return float64 arrays.
    for col in ("txn_count_30d", "distinct_counterparties_30d", "days_since_last_activity", "prior_sars_count", "account_age_days"):
        df[col] = df[col].round().astype(int)

    df.insert(0, "alert_id", range(1, len(df) + 1))
    df.insert(1, "customer_id", [f"CUST-{i:06d}" for i in range(1, len(df) + 1)])
    return df


def main() -> None:
    os.makedirs(ARTIFACTS_DIR, exist_ok=True)
    df = generate_alerts(n_per_typology=1500)
    out_path = os.path.join(ARTIFACTS_DIR, "alerts_dataset.csv")
    df.to_csv(out_path, index=False)

    meta = {
        "seed": RNG_SEED,
        "n_rows": len(df),
        "typologies": [t.name for t in TYPOLOGIES],
        "overall_true_positive_rate": round(float(df["is_true_positive"].mean()), 4),
        "per_typology_true_positive_rate": {
            t.name: round(float(df.loc[df["typology_hint"] == t.name, "is_true_positive"].mean()), 4) for t in TYPOLOGIES
        },
        "note": (
            "Entirely synthetic. No real bank, customer, or transaction data "
            "was used or could legally be used for a project like this."
        ),
    }
    with open(os.path.join(ARTIFACTS_DIR, "dataset_meta.json"), "w") as f:
        json.dump(meta, f, indent=2)

    print(f"Wrote {len(df)} rows to {out_path}")
    print(json.dumps(meta, indent=2))


if __name__ == "__main__":
    main()
