import os
import sys

import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "model"))
from generate_data import TYPOLOGIES, generate_alerts  # noqa: E402

from vigil.features import FEATURE_NAMES


def test_generated_dataset_has_all_feature_columns_with_no_missing_values():
    df = generate_alerts(n_per_typology=50, seed=1)
    for col in FEATURE_NAMES:
        assert col in df.columns
        assert df[col].isna().sum() == 0


def test_every_typology_is_represented_and_true_positive_rate_is_bounded():
    df = generate_alerts(n_per_typology=100, seed=1)
    assert set(df["typology_hint"]) == {t.name for t in TYPOLOGIES}
    overall_rate = df["is_true_positive"].mean()
    # Not close to 0 or 1 -- a dataset where the label is nearly
    # constant would make the whole modeling exercise meaningless.
    assert 0.05 < overall_rate < 0.4


def test_generation_is_deterministic_given_the_same_seed():
    df1 = generate_alerts(n_per_typology=50, seed=7)
    df2 = generate_alerts(n_per_typology=50, seed=7)
    pd.testing.assert_frame_equal(df1, df2)
