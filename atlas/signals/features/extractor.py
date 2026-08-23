"""Unified FeatureEngine orchestrating feature extraction, point-in-time joins, and feature storage."""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

import numpy as np
import pandas as pd

from atlas.core.context import MarketContext
from atlas.core.types import Symbol
from atlas.signals.features.breadth import MarketBreadthCalculator
from atlas.signals.features.cross_sectional import CrossSectionalRanker
from atlas.signals.features.technical import StatisticalFeatureExtractor


class FeatureEngine:
    """Orchestrates comprehensive L2 feature extraction across single symbols and universes."""

    def __init__(self) -> None:
        self.stat_extractor = StatisticalFeatureExtractor()
        self.cs_ranker = CrossSectionalRanker()
        self.breadth_calc = MarketBreadthCalculator()

    @property
    def all_feature_names(self) -> list[str]:
        """Full list of available feature names."""
        names = list(self.stat_extractor.feature_names)
        names.extend(
            [
                "cs_rank_momentum_12m_1m",
                "cs_rank_momentum_1m",
                "cs_rank_realized_vol_21d",
                "cs_rank_range_pos_52w",
                "cs_zscore_momentum_12m_1m",
                "cs_zscore_momentum_1m",
                "breadth_advance_decline",
                "breadth_pct_above_50d",
                "breadth_pct_above_200d",
                "breadth_avg_rsi",
                "breadth_return_dispersion_21d",
            ]
        )
        return names

    def extract_single_symbol_pit(self, ctx: MarketContext, symbol: Symbol) -> dict[str, float]:
        """Extract statistical and technical features for a single symbol at ctx.now."""
        return self.stat_extractor.extract_pit(ctx, symbol)

    def extract_universe_pit(
        self,
        ctx: MarketContext,
        universe: Sequence[Symbol],
    ) -> dict[Symbol, dict[str, float]]:
        """Extract complete combined (statistical + cross-sectional + breadth) feature vectors for universe."""
        cs_feats = self.cs_ranker.evaluate_universe_features(ctx, universe)
        breadth_feats = self.breadth_calc.compute_breadth(ctx, universe)

        res: dict[Symbol, dict[str, float]] = {}
        for sym in universe:
            sym_feats = self.stat_extractor.extract_pit(ctx, sym)
            combined = {**sym_feats, **cs_feats.get(sym, {}), **breadth_feats}
            res[sym] = combined

        return res

    def build_dataset_from_bars(
        self,
        symbol_bars_map: dict[Symbol, pd.DataFrame],
        forward_horizons: list[int] | None = None,
    ) -> pd.DataFrame:
        """Build a panel DataFrame of historical features and forward return targets for ML training.

        Target: `target_return_{k}d` and `target_dir_{k}d` (1 if positive, 0 otherwise).
        """
        if forward_horizons is None:
            forward_horizons = [5, 21]

        all_rows: list[pd.DataFrame] = []

        for sym, df_b in symbol_bars_map.items():
            if len(df_b) < 252:
                continue

            df = df_b.copy().sort_values("timestamp").reset_index(drop=True)
            feat_df = self.stat_extractor.extract_batch(df)
            feat_df["symbol"] = str(sym)
            feat_df["timestamp"] = df["timestamp"]
            feat_df["close"] = df["close"]

            # Compute forward return targets relative to executable t+1 open price
            close_arr = df["close"].to_numpy(dtype=float)
            open_arr = df["open"].to_numpy(dtype=float) if "open" in df.columns else close_arr
            n = len(df)
            for k in forward_horizons:
                fwd_ret = np.full(n, np.nan)
                fwd_dir = np.full(n, np.nan)
                for i in range(n - k):
                    # Execution on day i occurs at open[i + 1]
                    exec_price = (
                        open_arr[i + 1] if (i + 1 < n and open_arr[i + 1] > 0) else close_arr[i]
                    )
                    if exec_price > 0 and (i + k) < n:
                        ret_k = (close_arr[i + k] - exec_price) / exec_price
                        fwd_ret[i] = ret_k
                        fwd_dir[i] = 1.0 if ret_k > 0 else 0.0

                feat_df[f"target_return_{k}d"] = fwd_ret
                feat_df[f"target_dir_{k}d"] = fwd_dir

            all_rows.append(feat_df)

        if not all_rows:
            return pd.DataFrame()

        panel_df = pd.concat(all_rows, ignore_index=True)
        if "timestamp" in panel_df.columns:
            panel_df = panel_df.sort_values("timestamp").reset_index(drop=True)
        return panel_df

    def save_feature_snapshot(self, df: pd.DataFrame, file_path: Path) -> None:
        """Save feature DataFrame to Parquet format."""
        file_path.parent.mkdir(parents=True, exist_ok=True)
        df.to_parquet(file_path, index=False)

    def load_feature_snapshot(self, file_path: Path) -> pd.DataFrame:
        """Load feature DataFrame from Parquet format."""
        if not file_path.exists():
            raise FileNotFoundError(f"Feature snapshot not found: {file_path}")
        return pd.read_parquet(file_path)
