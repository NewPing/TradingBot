"""Pure indicator calculation routines with no external lookahead."""

from __future__ import annotations

import numpy as np
import numpy.typing as npt


def compute_sma(values: npt.NDArray[np.float64], period: int) -> float | None:
    """Compute Simple Moving Average of the last `period` elements."""
    if len(values) < period or period <= 0:
        return None
    return float(np.mean(values[-period:]))


def compute_ema(values: npt.NDArray[np.float64], period: int) -> float | None:
    """Compute Exponential Moving Average of the series up to the last element."""
    if len(values) < period or period <= 0:
        return None
    alpha = 2.0 / (period + 1.0)
    ema = float(values[0])
    for v in values[1:]:
        ema = alpha * float(v) + (1.0 - alpha) * ema
    return ema


def compute_rsi(closes: npt.NDArray[np.float64], period: int = 14) -> float | None:
    """Compute Wilder's Relative Strength Index (RSI)."""
    if len(closes) < period + 1 or period <= 0:
        return None

    diffs = np.diff(closes)
    gains = np.where(diffs > 0, diffs, 0.0)
    losses = np.where(diffs < 0, -diffs, 0.0)

    # Initial average
    avg_gain = float(np.mean(gains[:period]))
    avg_loss = float(np.mean(losses[:period]))

    # Wilder smoothing
    for i in range(period, len(diffs)):
        avg_gain = (avg_gain * (period - 1) + gains[i]) / period
        avg_loss = (avg_loss * (period - 1) + losses[i]) / period

    if avg_loss == 0.0:
        return 100.0 if avg_gain > 0.0 else 50.0

    rs = avg_gain / avg_loss
    rsi = 100.0 - (100.0 / (1.0 + rs))
    return float(rsi)


def compute_macd(
    closes: npt.NDArray[np.float64],
    fast_period: int = 12,
    slow_period: int = 26,
    signal_period: int = 9,
) -> tuple[float, float, float] | None:
    """Compute MACD (macd_line, signal_line, histogram)."""
    if len(closes) < slow_period + signal_period:
        return None

    # Calculate fast & slow EMA series
    alpha_fast = 2.0 / (fast_period + 1.0)
    alpha_slow = 2.0 / (slow_period + 1.0)

    ema_fast = float(closes[0])
    ema_slow = float(closes[0])
    macd_series: list[float] = []

    for c in closes:
        ema_fast = alpha_fast * float(c) + (1.0 - alpha_fast) * ema_fast
        ema_slow = alpha_slow * float(c) + (1.0 - alpha_slow) * ema_slow
        macd_series.append(ema_fast - ema_slow)

    macd_arr = np.array(macd_series, dtype=np.float64)
    # Signal line is EMA of macd_series
    alpha_sig = 2.0 / (signal_period + 1.0)
    ema_sig = float(macd_arr[0])
    for m in macd_arr[1:]:
        ema_sig = alpha_sig * float(m) + (1.0 - alpha_sig) * ema_sig

    macd_line = float(macd_arr[-1])
    sig_line = float(ema_sig)
    hist = macd_line - sig_line
    return (macd_line, sig_line, hist)


def compute_atr(
    highs: npt.NDArray[np.float64],
    lows: npt.NDArray[np.float64],
    closes: npt.NDArray[np.float64],
    period: int = 14,
) -> float | None:
    """Compute Average True Range (ATR)."""
    if len(closes) < period + 1 or period <= 0:
        return None

    tr_list: list[float] = []
    for i in range(1, len(closes)):
        h = float(highs[i])
        low_val = float(lows[i])
        prev_c = float(closes[i - 1])
        tr = max(h - low_val, abs(h - prev_c), abs(low_val - prev_c))
        tr_list.append(tr)

    tr_arr = np.array(tr_list, dtype=np.float64)
    # Wilder smoothed ATR
    atr = float(np.mean(tr_arr[:period]))
    for i in range(period, len(tr_arr)):
        atr = (atr * (period - 1) + tr_arr[i]) / period

    return float(atr)


def compute_bollinger_bands(
    closes: npt.NDArray[np.float64],
    period: int = 20,
    num_std: float = 2.0,
) -> tuple[float, float, float, float] | None:
    """Compute Bollinger Bands (middle, upper, lower, percent_b)."""
    if len(closes) < period or period <= 0:
        return None

    window = closes[-period:]
    middle = float(np.mean(window))
    std = float(np.std(window, ddof=1)) if len(window) > 1 else 0.0
    upper = middle + num_std * std
    lower = middle - num_std * std

    current_price = float(closes[-1])
    band_width = upper - lower
    percent_b = (current_price - lower) / band_width if band_width > 0.0 else 0.5

    return (middle, upper, lower, percent_b)


def compute_momentum_roc(
    closes: npt.NDArray[np.float64],
    lookback: int = 252,
    skip: int = 21,
) -> float | None:
    """Compute Rate of Change / Momentum over lookback periods skipping most recent skip periods.

    Momentum = (Price[t - skip] / Price[t - lookback]) - 1.0
    """
    total_needed = lookback + 1
    if len(closes) < total_needed or lookback <= skip:
        return None

    # Price at t - skip
    idx_recent = -1 - skip
    # Price at t - lookback
    idx_base = -1 - lookback

    price_recent = float(closes[idx_recent])
    price_base = float(closes[idx_base])

    if price_base <= 0.0:
        return None

    return (price_recent / price_base) - 1.0


def compute_realized_volatility(
    closes: npt.NDArray[np.float64],
    period: int = 20,
    annualization_factor: float = 252.0,
) -> float | None:
    """Compute annualized realized standard deviation of log returns."""
    if len(closes) < period + 1 or period < 2:
        return None

    window = closes[-(period + 1) :]
    log_returns = np.diff(np.log(window))
    daily_vol = float(np.std(log_returns, ddof=1))
    return float(daily_vol * np.sqrt(annualization_factor))


def compute_52w_position(
    closes: npt.NDArray[np.float64],
    period: int = 252,
) -> float | None:
    """Compute price position relative to 52-week high/low range: (Close - Low) / (High - Low)."""
    if len(closes) < period or period <= 0:
        return None

    window = closes[-period:]
    low_52 = float(np.min(window))
    high_52 = float(np.max(window))
    current_price = float(closes[-1])

    rng = high_52 - low_52
    if rng <= 0.0:
        return 0.5

    pos = (current_price - low_52) / rng
    return float(np.clip(pos, 0.0, 1.0))


def compute_volume_zscore(
    volumes: npt.NDArray[np.float64],
    period: int = 20,
) -> float | None:
    """Compute z-score of the most recent volume relative to trailing rolling mean & std."""
    if len(volumes) < period or period < 2:
        return None

    window = volumes[-period:]
    mean_vol = float(np.mean(window))
    std_vol = float(np.std(window, ddof=1))

    if std_vol <= 0.0:
        return 0.0

    current_vol = float(volumes[-1])
    return float((current_vol - mean_vol) / std_vol)
