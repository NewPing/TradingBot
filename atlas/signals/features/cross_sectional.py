"""Cross-sectional universe feature ranker and normalizer."""

from __future__ import annotations

from collections.abc import Sequence

import numpy as np
import pandas as pd

from atlas.core.context import MarketContext
from atlas.core.types import Symbol


class CrossSectionalRanker:
    """Computes point-in-time cross-sectional percentile ranks and z-scores across a universe."""

    @staticmethod
    def compute_ranks(values: dict[Symbol, float]) -> dict[Symbol, float]:
        """Convert a dictionary of {symbol: raw_metric} to normalized percentile ranks [0.0..1.0]."""
        if len(values) < 2:
            return dict.fromkeys(values, 0.5)

        valid_items = [(s, v) for s, v in values.items() if not (pd.isna(v) or np.isnan(v))]
        if len(valid_items) < 2:
            return dict.fromkeys(values, 0.5)

        s_series = pd.Series(dict(valid_items))
        ranks = s_series.rank(pct=True, method="average")
        return {s: float(ranks.get(s, 0.5)) for s in values}

    @staticmethod
    def compute_zscores(values: dict[Symbol, float], clip: float = 3.0) -> dict[Symbol, float]:
        """Convert a dictionary of {symbol: raw_metric} to cross-sectional z-scores clipped to [-clip, +clip]."""
        if len(values) < 2:
            return dict.fromkeys(values, 0.0)

        valid_items = [(s, v) for s, v in values.items() if not (pd.isna(v) or np.isnan(v))]
        if len(valid_items) < 2:
            return dict.fromkeys(values, 0.0)

        s_series = pd.Series(dict(valid_items))
        mean = float(s_series.mean())
        std = float(s_series.std(ddof=1))
        if std < 1e-8:
            return dict.fromkeys(values, 0.0)

        z = (s_series - mean) / std
        clipped = z.clip(lower=-clip, upper=clip)
        return {s: float(clipped.get(s, 0.0)) for s in values}

    def evaluate_universe_features(
        self,
        ctx: MarketContext,
        universe: Sequence[Symbol],
    ) -> dict[Symbol, dict[str, float]]:
        """Compute all cross-sectional features for universe strictly at ctx.now."""
        raw_mom_12m: dict[Symbol, float] = {}
        raw_mom_1m: dict[Symbol, float] = {}
        raw_vol_21d: dict[Symbol, float] = {}
        raw_range_52w: dict[Symbol, float] = {}

        for sym in universe:
            df = ctx.bars(sym, lookback=260)
            if df.is_empty() or len(df) < 22:
                continue

            closes = df["close"].to_numpy().astype(float)
            highs = df["high"].to_numpy().astype(float)
            lows = df["low"].to_numpy().astype(float)
            n = len(closes)

            # 1m momentum (21 bars)
            if n >= 22 and closes[-22] > 0:
                raw_mom_1m[sym] = (closes[-1] - closes[-22]) / closes[-22]

            # 12m-1m momentum (252 to 21 bars ago, damped for shorter histories)
            if n >= 253 and closes[-253] > 0:
                raw_mom_12m[sym] = (closes[-22] - closes[-253]) / closes[-253]
            elif n >= 63 and closes[0] > 0:
                elapsed_days = max(1, n - 22)
                cum_ret = (closes[-22] - closes[0]) / closes[0]
                # Linear scaling with sample size square-root damping to prevent short-history distortion
                raw_mom_12m[sym] = float(cum_ret * ((elapsed_days / 231.0) ** 0.5))

            # 21d realized vol
            if n >= 22:
                rets = [
                    (closes[i] - closes[i - 1]) / closes[i - 1]
                    for i in range(n - 21, n)
                    if closes[i - 1] > 0
                ]
                if len(rets) > 5:
                    raw_vol_21d[sym] = float(np.std(rets, ddof=1)) * np.sqrt(252.0)

            # 52w range position
            lookback_hl = min(n, 252)
            h_max = max(highs[-lookback_hl:])
            l_min = min(lows[-lookback_hl:])
            rng = h_max - l_min
            if rng > 1e-6:
                raw_range_52w[sym] = (closes[-1] - l_min) / rng

        # Compute ranks
        rank_mom_12m = self.compute_ranks(raw_mom_12m)
        rank_mom_1m = self.compute_ranks(raw_mom_1m)
        rank_vol_21d = self.compute_ranks(raw_vol_21d)
        rank_range_52w = self.compute_ranks(raw_range_52w)

        # Compute z-scores
        zscore_mom_12m = self.compute_zscores(raw_mom_12m)
        zscore_mom_1m = self.compute_zscores(raw_mom_1m)

        res: dict[Symbol, dict[str, float]] = {}
        for sym in universe:
            res[sym] = {
                "cs_rank_momentum_12m_1m": rank_mom_12m.get(sym, 0.5),
                "cs_rank_momentum_1m": rank_mom_1m.get(sym, 0.5),
                "cs_rank_realized_vol_21d": rank_vol_21d.get(sym, 0.5),
                "cs_rank_range_pos_52w": rank_range_52w.get(sym, 0.5),
                "cs_zscore_momentum_12m_1m": zscore_mom_12m.get(sym, 0.0),
                "cs_zscore_momentum_1m": zscore_mom_1m.get(sym, 0.0),
            }

        return res
