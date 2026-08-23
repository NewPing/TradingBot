"""Purged and Embargoed K-Fold Cross-Validation for Financial Time Series."""

from __future__ import annotations

from collections.abc import Iterator

import numpy as np
import pandas as pd


class PurgedKFoldCV:
    """Purged and Embargoed K-Fold Cross-Validation (López de Prado methodology).

    Prevents lookahead leakage from overlapping label evaluation windows across train/test splits,
    and applies an embargo period after the test set to eliminate serial correlation leakage.
    """

    def __init__(
        self,
        n_splits: int = 5,
        t1: pd.Series | None = None,
        pct_embargo: float = 0.01,
        embargo_bars: int | None = None,
    ) -> None:
        """Initialize Purged K-Fold CV.

        Args:
            n_splits: Number of cross-validation folds.
            t1: Series where index is observation timestamp and value is label end-time (t + horizon).
            pct_embargo: Embargo fraction of total time-series length applied after test folds.
            embargo_bars: Fixed number of bars for embargo (overrides pct_embargo if specified).
        """
        if n_splits < 2:
            raise ValueError(f"n_splits must be at least 2, got {n_splits}")
        self.n_splits = n_splits
        self.t1 = t1
        self.pct_embargo = pct_embargo
        self.embargo_bars = embargo_bars

    def split(
        self,
        X: pd.DataFrame | np.ndarray,
        y: pd.Series | np.ndarray | None = None,
        groups: np.ndarray | None = None,
    ) -> Iterator[tuple[np.ndarray, np.ndarray]]:
        """Generate indices to split data into training and test sets.

        Yields:
            (train_indices, test_indices) tuples of numpy integer arrays.
        """
        _ = y
        _ = groups
        n_samples = len(X)
        if n_samples < self.n_splits:
            raise ValueError(
                f"Sample size ({n_samples}) cannot be smaller than n_splits ({self.n_splits})"
            )

        # Determine timestamps / time index
        if isinstance(X, pd.DataFrame) and "timestamp" in X.columns:
            times = pd.to_datetime(X["timestamp"])
        elif isinstance(X, pd.DataFrame) and isinstance(X.index, pd.DatetimeIndex):
            times = pd.Series(X.index)
        else:
            # Fallback to integer sequence as synthetic time
            times = pd.Series(np.arange(n_samples))

        # Determine label end times t1 (defaulting to same-bar if not provided)
        t1_series = self.t1 if self.t1 is not None else times

        # Compute embargo length in number of bars
        if self.embargo_bars is not None:
            embargo_len = self.embargo_bars
        else:
            embargo_len = int(n_samples * self.pct_embargo)

        indices = np.arange(n_samples)
        # Uniform contiguous chunks for test splits
        chunk_size = n_samples // self.n_splits

        for fold in range(self.n_splits):
            test_start = fold * chunk_size
            test_end = n_samples if fold == self.n_splits - 1 else (fold + 1) * chunk_size
            test_idx = indices[test_start:test_end]

            test_times = times.iloc[test_idx]
            test_t0 = test_times.min()
            test_t1 = t1_series.iloc[test_idx].max()

            # 1. Purging: find train indices where sample window does NOT overlap [test_t0, test_t1]
            train_mask = np.ones(n_samples, dtype=bool)
            train_mask[test_start:test_end] = False  # Remove test fold itself

            for i in range(n_samples):
                if not train_mask[i]:
                    continue
                obs_t0 = times.iloc[i]
                obs_t1 = t1_series.iloc[i]

                # Check overlap between [obs_t0, obs_t1] and [test_t0, test_t1]
                if obs_t0 <= test_t1 and obs_t1 >= test_t0:
                    train_mask[i] = False

            # 2. Embargo: quarantine training samples immediately following test partition
            if embargo_len > 0 and test_end < n_samples:
                embargo_end = min(n_samples, test_end + embargo_len)
                train_mask[test_end:embargo_end] = False

            train_idx = indices[train_mask]
            yield train_idx, test_idx
