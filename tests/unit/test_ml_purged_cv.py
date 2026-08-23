"""Unit and property tests for Purged K-Fold Cross-Validation with Embargo."""

from __future__ import annotations

import numpy as np
import pandas as pd

from atlas.ml.validation import PurgedKFoldCV


def test_purged_kfold_split_counts() -> None:
    n = 200
    df = pd.DataFrame(
        {
            "timestamp": pd.date_range("2015-01-01", periods=n, freq="B"),
            "val": np.random.randn(n),
        }
    )
    cv = PurgedKFoldCV(n_splits=5, embargo_bars=5)
    splits = list(cv.split(df))

    assert len(splits) == 5
    for tr, te in splits:
        assert len(tr) > 0
        assert len(te) > 0
        # Assert no overlap between train and test
        assert len(set(tr).intersection(set(te))) == 0


def test_purged_kfold_embargo_quarantine() -> None:
    n = 100
    df = pd.DataFrame(
        {
            "timestamp": pd.date_range("2015-01-01", periods=n, freq="B"),
            "val": np.random.randn(n),
        }
    )
    embargo = 5
    cv = PurgedKFoldCV(n_splits=4, embargo_bars=embargo)
    splits = list(cv.split(df))

    # Fold 0 test split covers indices 0..24
    tr0, te0 = splits[0]
    # Indices 25..(25+5-1)=25..29 should be quarantined by the embargo
    for q_idx in range(25, 25 + embargo):
        assert q_idx not in tr0


def test_purged_kfold_label_overlap_purging() -> None:
    n = 50
    times = pd.date_range("2020-01-01", periods=n, freq="D")
    # Observation at i has label window ending at i + 3 days
    t1 = times + pd.Timedelta(days=3)
    t1_series = pd.Series(t1, index=times)

    df = pd.DataFrame({"timestamp": times, "feat": np.arange(n)})
    cv = PurgedKFoldCV(n_splits=5, t1=t1_series, embargo_bars=2)
    splits = list(cv.split(df))

    for tr, te in splits:
        test_start_time = times[te[0]]
        test_end_time = t1_series.iloc[te].max()
        for tr_idx in tr:
            tr_t0 = times[tr_idx]
            tr_t1 = t1_series.iloc[tr_idx]
            # Verify that training window does not overlap with test window
            has_overlap = (tr_t0 <= test_end_time) and (tr_t1 >= test_start_time)
            assert not has_overlap
