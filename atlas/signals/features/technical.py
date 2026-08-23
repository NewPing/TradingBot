"""Statistical and technical feature extractors for market data series."""

from __future__ import annotations

import math
from typing import Any

import numpy as np
import pandas as pd

from atlas.core.context import MarketContext
from atlas.core.types import Symbol
from atlas.signals.features.base import FeatureExtractor, FeatureMetadata


class StatisticalFeatureExtractor(FeatureExtractor):
    """Computes comprehensive suite of single-instrument statistical & technical features."""

    def __init__(self, max_lookback: int = 252) -> None:
        self._max_lookback = max(max_lookback, 252)

    @property
    def warmup_bars(self) -> int:
        return self._max_lookback + 20

    @property
    def feature_names(self) -> list[str]:
        return [
            "return_1d",
            "return_5d",
            "return_21d",
            "return_63d",
            "momentum_12m_1m",
            "realized_vol_21d",
            "realized_vol_63d",
            "garman_klass_vol_21d",
            "parkinson_vol_21d",
            "atr_norm_14d",
            "sma_dist_20d",
            "sma_dist_50d",
            "sma_dist_200d",
            "macd_hist_zscore",
            "bollinger_pct_b",
            "bollinger_bandwidth",
            "rsi_14d",
            "rsi_2d",
            "range_pos_52w",
            "volume_zscore_20d",
        ]

    def metadata(self) -> list[FeatureMetadata]:
        return [
            FeatureMetadata("return_1d", "1-day percentage return", "statistical", 2, -1.0, 5.0),
            FeatureMetadata("return_5d", "5-day percentage return", "statistical", 6, -1.0, 10.0),
            FeatureMetadata(
                "return_21d", "21-day (1-month) percentage return", "statistical", 22, -1.0, 20.0
            ),
            FeatureMetadata(
                "return_63d", "63-day (3-month) percentage return", "statistical", 64, -1.0, 50.0
            ),
            FeatureMetadata(
                "momentum_12m_1m",
                "12-month return with 1-month skip",
                "statistical",
                253,
                -1.0,
                100.0,
            ),
            FeatureMetadata(
                "realized_vol_21d",
                "21-day annualized close-to-close realized volatility",
                "statistical",
                22,
                0.0,
                10.0,
            ),
            FeatureMetadata(
                "realized_vol_63d",
                "63-day annualized close-to-close realized volatility",
                "statistical",
                64,
                0.0,
                10.0,
            ),
            FeatureMetadata(
                "garman_klass_vol_21d",
                "21-day Garman-Klass OHLC annualized volatility",
                "statistical",
                22,
                0.0,
                10.0,
            ),
            FeatureMetadata(
                "parkinson_vol_21d",
                "21-day Parkinson HL annualized volatility",
                "statistical",
                22,
                0.0,
                10.0,
            ),
            FeatureMetadata(
                "atr_norm_14d",
                "14-day Average True Range normalized by close price",
                "technical",
                15,
                0.0,
                1.0,
            ),
            FeatureMetadata(
                "sma_dist_20d",
                "Percentage distance of close from 20-day SMA",
                "technical",
                20,
                -1.0,
                5.0,
            ),
            FeatureMetadata(
                "sma_dist_50d",
                "Percentage distance of close from 50-day SMA",
                "technical",
                50,
                -1.0,
                10.0,
            ),
            FeatureMetadata(
                "sma_dist_200d",
                "Percentage distance of close from 200-day SMA",
                "technical",
                200,
                -1.0,
                20.0,
            ),
            FeatureMetadata(
                "macd_hist_zscore",
                "MACD histogram (12, 26, 9) rolling 63d z-score",
                "technical",
                90,
                -5.0,
                5.0,
            ),
            FeatureMetadata(
                "bollinger_pct_b",
                "Bollinger Band (20, 2) %b oscillator",
                "technical",
                20,
                -1.0,
                2.0,
            ),
            FeatureMetadata(
                "bollinger_bandwidth",
                "Bollinger Band (20, 2) bandwidth (upper-lower)/middle",
                "technical",
                20,
                0.0,
                5.0,
            ),
            FeatureMetadata(
                "rsi_14d",
                "14-day Relative Strength Index (0..100)",
                "technical",
                15,
                0.0,
                100.0,
                is_normalized=True,
            ),
            FeatureMetadata(
                "rsi_2d",
                "2-day Relative Strength Index for short-term mean reversion (0..100)",
                "technical",
                3,
                0.0,
                100.0,
                is_normalized=True,
            ),
            FeatureMetadata(
                "range_pos_52w",
                "Position within 52-week High/Low range (0..1)",
                "technical",
                252,
                0.0,
                1.0,
                is_normalized=True,
            ),
            FeatureMetadata(
                "volume_zscore_20d", "20-day Volume Z-score", "statistical", 20, -5.0, 10.0
            ),
        ]

    def extract_pit(self, ctx: MarketContext, symbol: Symbol) -> dict[str, float]:
        """Extract latest feature dictionary strictly at or before ctx.now."""
        df_pl = ctx.bars(symbol, lookback=self.warmup_bars, adjusted=True)
        if df_pl.is_empty() or len(df_pl) < self._max_lookback:
            return dict.fromkeys(self.feature_names, 0.0)

        try:
            df_pandas = df_pl.to_pandas()
        except Exception:
            df_pandas = pd.DataFrame(df_pl.to_dicts())

        batch_df = self.extract_batch(df_pandas)
        if batch_df.empty:
            return dict.fromkeys(self.feature_names, 0.0)
        latest_row = batch_df.iloc[-1]
        return {
            name: float(latest_row.get(name, 0.0)) if not pd.isna(latest_row.get(name)) else 0.0
            for name in self.feature_names
        }

    def extract_batch(self, df_bars: pd.DataFrame) -> pd.DataFrame:
        """Extract full time-series feature matrix from historical bars DataFrame."""
        if len(df_bars) == 0:
            return pd.DataFrame(columns=self.feature_names)

        df = df_bars.copy()
        close = df["close"].to_numpy(dtype=float)
        high = df["high"].to_numpy(dtype=float)
        low = df["low"].to_numpy(dtype=float)
        open_ = df["open"].to_numpy(dtype=float)
        volume = df["volume"].to_numpy(dtype=float)
        n = len(df)

        res: dict[str, np.ndarray[Any, Any]] = {}

        # 1. Multi-horizon Returns
        res["return_1d"] = np.zeros(n)
        res["return_5d"] = np.zeros(n)
        res["return_21d"] = np.zeros(n)
        res["return_63d"] = np.zeros(n)
        res["momentum_12m_1m"] = np.zeros(n)

        for i in range(1, n):
            if close[i - 1] > 0:
                res["return_1d"][i] = (close[i] - close[i - 1]) / close[i - 1]
        for i in range(5, n):
            if close[i - 5] > 0:
                res["return_5d"][i] = (close[i] - close[i - 5]) / close[i - 5]
        for i in range(21, n):
            if close[i - 21] > 0:
                res["return_21d"][i] = (close[i] - close[i - 21]) / close[i - 21]
        for i in range(63, n):
            if close[i - 63] > 0:
                res["return_63d"][i] = (close[i] - close[i - 63]) / close[i - 63]
        for i in range(252, n):
            if close[i - 252] > 0:
                res["momentum_12m_1m"][i] = (close[i - 21] - close[i - 252]) / close[i - 252]

        # 2. Realized Volatility (close-to-close)
        ret1 = res["return_1d"]
        res["realized_vol_21d"] = np.zeros(n)
        res["realized_vol_63d"] = np.zeros(n)
        sqrt_252 = math.sqrt(252.0)

        for i in range(21, n):
            window = ret1[i - 20 : i + 1]
            std = float(np.std(window, ddof=1)) if len(window) > 1 else 0.0
            res["realized_vol_21d"][i] = std * sqrt_252

        for i in range(63, n):
            window = ret1[i - 62 : i + 1]
            std = float(np.std(window, ddof=1)) if len(window) > 1 else 0.0
            res["realized_vol_63d"][i] = std * sqrt_252

        # 3. Garman-Klass & Parkinson Volatility
        res["garman_klass_vol_21d"] = np.zeros(n)
        res["parkinson_vol_21d"] = np.zeros(n)

        gk_term = np.zeros(n)
        park_term = np.zeros(n)
        inv_4ln2 = 1.0 / (4.0 * math.log(2.0))
        c_gk = 2.0 * math.log(2.0) - 1.0

        for i in range(n):
            h_l = max(high[i], low[i] + 1e-6) / max(low[i], 1e-6)
            c_o = max(close[i], 1e-6) / max(open_[i], 1e-6)
            log_hl = math.log(h_l)
            log_co = math.log(c_o)

            gk_term[i] = 0.5 * (log_hl**2) - c_gk * (log_co**2)
            park_term[i] = inv_4ln2 * (log_hl**2)

        for i in range(21, n):
            gk_mean = float(np.mean(gk_term[i - 20 : i + 1]))
            park_mean = float(np.mean(park_term[i - 20 : i + 1]))
            res["garman_klass_vol_21d"][i] = math.sqrt(max(0.0, gk_mean)) * sqrt_252
            res["parkinson_vol_21d"][i] = math.sqrt(max(0.0, park_mean)) * sqrt_252

        # 4. Normalized ATR (Wilder's smoothed)
        res["atr_norm_14d"] = np.zeros(n)
        tr = np.zeros(n)
        for i in range(n):
            if i == 0:
                tr[i] = high[i] - low[i]
            else:
                tr[i] = max(
                    high[i] - low[i],
                    abs(high[i] - close[i - 1]),
                    abs(low[i] - close[i - 1]),
                )
        if n >= 15:
            current_atr = float(np.mean(tr[1:15]))
            res["atr_norm_14d"][14] = (current_atr / close[14]) if close[14] > 0 else 0.0
            for i in range(15, n):
                current_atr = (current_atr * 13.0 + tr[i]) / 14.0
                res["atr_norm_14d"][i] = (current_atr / close[i]) if close[i] > 0 else 0.0

        # 5. SMA Distances
        res["sma_dist_20d"] = np.zeros(n)
        res["sma_dist_50d"] = np.zeros(n)
        res["sma_dist_200d"] = np.zeros(n)

        for i in range(20, n):
            sma = float(np.mean(close[i - 19 : i + 1]))
            res["sma_dist_20d"][i] = (close[i] - sma) / sma if sma > 0 else 0.0

        for i in range(50, n):
            sma = float(np.mean(close[i - 49 : i + 1]))
            res["sma_dist_50d"][i] = (close[i] - sma) / sma if sma > 0 else 0.0

        for i in range(200, n):
            sma = float(np.mean(close[i - 199 : i + 1]))
            res["sma_dist_200d"][i] = (close[i] - sma) / sma if sma > 0 else 0.0

        # 6. MACD Histogram Z-Score
        res["macd_hist_zscore"] = np.zeros(n)
        ema12 = _calc_ema(close, 12)
        ema26 = _calc_ema(close, 26)
        macd_line = ema12 - ema26
        signal_line = _calc_ema(macd_line, 9)
        macd_hist = macd_line - signal_line

        for i in range(63, n):
            hist_win = macd_hist[i - 62 : i + 1]
            std_h = float(np.std(hist_win, ddof=1))
            mean_h = float(np.mean(hist_win))
            res["macd_hist_zscore"][i] = (macd_hist[i] - mean_h) / std_h if std_h > 1e-8 else 0.0

        # 7. Bollinger %b and Bandwidth
        res["bollinger_pct_b"] = np.zeros(n)
        res["bollinger_bandwidth"] = np.zeros(n)

        for i in range(20, n):
            win = close[i - 19 : i + 1]
            mean_c = float(np.mean(win))
            std_c = float(np.std(win, ddof=1))
            upper = mean_c + 2.0 * std_c
            lower = mean_c - 2.0 * std_c
            band_width = upper - lower
            res["bollinger_pct_b"][i] = (
                (close[i] - lower) / band_width if band_width > 1e-8 else 0.5
            )
            res["bollinger_bandwidth"][i] = band_width / mean_c if mean_c > 0 else 0.0

        # 8. RSI 14 & RSI 2
        res["rsi_14d"] = _calc_rsi(close, 14)
        res["rsi_2d"] = _calc_rsi(close, 2)

        # 9. 52-week Range Position
        res["range_pos_52w"] = np.zeros(n)
        for i in range(251, n):
            h_win = float(np.max(high[max(0, i - 251) : i + 1]))
            l_win = float(np.min(low[max(0, i - 251) : i + 1]))
            rng = h_win - l_win
            res["range_pos_52w"][i] = (close[i] - l_win) / rng if rng > 1e-8 else 0.5

        # 10. Volume Z-Score 20d (baseline on prior 20 bars excluding current bar)
        res["volume_zscore_20d"] = np.zeros(n)
        for i in range(21, n):
            v_win = volume[i - 20 : i]
            mean_v = float(np.mean(v_win))
            std_v = float(np.std(v_win, ddof=1))
            res["volume_zscore_20d"][i] = (volume[i] - mean_v) / std_v if std_v > 1e-8 else 0.0

        out_df = pd.DataFrame(res, index=df.index)
        return out_df


def _calc_ema(data: np.ndarray[Any, Any], span: int) -> np.ndarray[Any, Any]:
    """Calculate exponential moving average seeded with initial mean."""
    n = len(data)
    ema = np.zeros(n)
    if n == 0:
        return ema
    if n < span:
        ema[:] = np.mean(data)
        return ema
    alpha = 2.0 / (span + 1.0)
    ema[span - 1] = float(np.mean(data[:span]))
    for i in range(span, n):
        ema[i] = alpha * data[i] + (1.0 - alpha) * ema[i - 1]
    # Backfill warm-up period
    for i in range(span - 2, -1, -1):
        ema[i] = ema[span - 1]
    return ema


def _calc_rsi(close: np.ndarray[Any, Any], period: int) -> np.ndarray[Any, Any]:
    """Calculate Relative Strength Index (0..100)."""
    n = len(close)
    rsi = np.full(n, 50.0)
    if n <= period:
        return rsi

    gains = np.zeros(n)
    losses = np.zeros(n)
    for i in range(1, n):
        diff = close[i] - close[i - 1]
        if diff > 0:
            gains[i] = diff
        else:
            losses[i] = abs(diff)

    avg_gain = float(np.mean(gains[1 : period + 1]))
    avg_loss = float(np.mean(losses[1 : period + 1]))

    for i in range(period, n):
        if i > period:
            avg_gain = (avg_gain * (period - 1) + gains[i]) / period
            avg_loss = (avg_loss * (period - 1) + losses[i]) / period

        if avg_loss < 1e-8:
            rsi[i] = 100.0 if avg_gain > 0 else 50.0
        else:
            rs = avg_gain / avg_loss
            rsi[i] = 100.0 - (100.0 / (1.0 + rs))

    return rsi
