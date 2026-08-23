"""Market breadth and macro context feature calculators."""

from __future__ import annotations

from collections.abc import Sequence

import numpy as np

from atlas.core.context import MarketContext
from atlas.core.types import Symbol


class MarketBreadthCalculator:
    """Calculates Point-in-Time market breadth metrics across the active equity universe."""

    def compute_breadth(
        self,
        ctx: MarketContext,
        universe: Sequence[Symbol],
    ) -> dict[str, float]:
        """Compute point-in-time universe breadth metrics strictly at ctx.now."""
        if not universe:
            return {
                "breadth_advance_decline": 0.5,
                "breadth_pct_above_50d": 0.5,
                "breadth_pct_above_200d": 0.5,
                "breadth_avg_rsi": 50.0,
                "breadth_return_dispersion_21d": 0.0,
            }

        advances = 0
        declines = 0
        above_50 = 0
        above_200 = 0
        total_50 = 0
        total_200 = 0
        rsi_vals: list[float] = []
        ret_21d_vals: list[float] = []

        for sym in universe:
            df = ctx.bars(sym, lookback=210)
            if df.is_empty():
                continue

            closes = df["close"].to_numpy().astype(float)
            n = len(closes)

            # 1d return
            if n >= 2:
                ret1 = (closes[-1] - closes[-2]) / closes[-2]
                if ret1 > 0:
                    advances += 1
                elif ret1 < 0:
                    declines += 1

            # 21d return
            if n >= 22 and closes[-22] > 0:
                ret_21d_vals.append((closes[-1] - closes[-22]) / closes[-22])

            # 50d SMA
            if n >= 50:
                sma50 = float(np.mean(closes[-50:]))
                total_50 += 1
                if closes[-1] > sma50:
                    above_50 += 1

            # 200d SMA
            if n >= 200:
                sma200 = float(np.mean(closes[-200:]))
                total_200 += 1
                if closes[-1] > sma200:
                    above_200 += 1

            # Approximate RSI 14
            if n >= 15:
                diffs = [closes[i] - closes[i - 1] for i in range(n - 14, n)]
                gains = [d for d in diffs if d > 0]
                losses = [abs(d) for d in diffs if d < 0]
                avg_g = sum(gains) / 14.0
                avg_l = sum(losses) / 14.0
                if avg_l < 1e-8:
                    rsi = 100.0 if avg_g > 0 else 50.0
                else:
                    rsi = 100.0 - (100.0 / (1.0 + (avg_g / avg_l)))
                rsi_vals.append(rsi)

        total_pairs = advances + declines
        ad_ratio = (advances / total_pairs) if total_pairs > 0 else 0.5
        pct_50 = (above_50 / total_50) if total_50 > 0 else 0.5
        pct_200 = (above_200 / total_200) if total_200 > 0 else 0.5
        avg_rsi = float(np.mean(rsi_vals)) if rsi_vals else 50.0
        dispersion = float(np.std(ret_21d_vals, ddof=1)) if len(ret_21d_vals) > 1 else 0.0

        return {
            "breadth_advance_decline": ad_ratio,
            "breadth_pct_above_50d": pct_50,
            "breadth_pct_above_200d": pct_200,
            "breadth_avg_rsi": avg_rsi,
            "breadth_return_dispersion_21d": dispersion,
        }
