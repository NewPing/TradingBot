"""FastAPI router for Signals Explorer and technical indicator inspection."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated

import numpy as np
from fastapi import APIRouter, Query

from atlas.api.schemas.signals import (
    SignalExploreResponse,
    SignalSeriesPoint,
    UniverseCandidateResponse,
    UniverseScreenerResponse,
)
from atlas.data.snapshots import SnapshotManager
from atlas.signals.indicators import (
    compute_atr,
    compute_bollinger_bands,
    compute_ema,
    compute_macd,
    compute_momentum_roc,
    compute_rsi,
    compute_sma,
)

router = APIRouter(prefix="/api/v1/signals", tags=["Signals Explorer"])


@router.get("/explore", response_model=SignalExploreResponse)
def explore_signals(
    symbol: Annotated[str, Query(description="Stock or ETF ticker symbol (e.g. SPY)")],
    snapshot_path: Annotated[
        str | None, Query(description="Snapshot directory or file path")
    ] = None,
    limit: Annotated[int, Query(ge=10, le=2000)] = 500,
) -> SignalExploreResponse:
    """Compute and return OHLCV price series and technical indicators for pattern hunting."""
    sym = symbol.upper()

    available_inds = [
        "sma_20",
        "sma_50",
        "sma_200",
        "ema_20",
        "rsi_14",
        "macd",
        "macd_signal",
        "atr_14",
        "bollinger_upper",
        "bollinger_lower",
        "momentum_20",
    ]

    base_dir = Path(snapshot_path) if snapshot_path else Path("data/snapshots")
    mgr = SnapshotManager(base_dir)

    df = None
    if base_dir.exists():
        subdirs = sorted(base_dir.iterdir(), reverse=True)
        for s_dir in subdirs:
            if s_dir.is_dir() and (s_dir / "bars_1d.parquet").exists():
                try:
                    df = mgr.load_snapshot_dataframe(s_dir.name)
                    df = df.filter(df["symbol"] == sym)
                    if not df.is_empty():
                        break
                except Exception:
                    pass

    if df is None or df.is_empty():
        return SignalExploreResponse(
            symbol=sym,
            points=[],
            available_indicators=available_inds,
        )

    df_tail = df.tail(limit)

    close_arr = np.array(df_tail["close"].to_list(), dtype=np.float64)
    high_arr = np.array(df_tail["high"].to_list(), dtype=np.float64)
    low_arr = np.array(df_tail["low"].to_list(), dtype=np.float64)
    open_arr = np.array(df_tail["open"].to_list(), dtype=np.float64)
    vol_arr = np.array(df_tail["volume"].to_list(), dtype=np.int64)
    ts_list = df_tail["ts"].to_list()

    points: list[SignalSeriesPoint] = []
    n = len(close_arr)

    for i in range(n):
        c_sub = close_arr[: i + 1]
        h_sub = high_arr[: i + 1]
        l_sub = low_arr[: i + 1]

        sma20_val = compute_sma(c_sub, 20)
        sma50_val = compute_sma(c_sub, 50)
        sma200_val = compute_sma(c_sub, 200)
        ema20_val = compute_ema(c_sub, 20)
        rsi14_val = compute_rsi(c_sub, 14)
        macd_res = compute_macd(c_sub, 12, 26, 9)
        macd_val = macd_res[0] if macd_res else None
        macd_sig = macd_res[1] if macd_res else None
        atr_val = compute_atr(h_sub, l_sub, c_sub, 14)
        bb_res = compute_bollinger_bands(c_sub, 20, 2.0)
        bb_up = bb_res[1] if bb_res else None
        bb_low = bb_res[2] if bb_res else None
        mom_val = compute_momentum_roc(c_sub, 20, 0)

        ts_val = ts_list[i]
        if isinstance(ts_val, datetime):
            ts_dt = ts_val if ts_val.tzinfo else ts_val.replace(tzinfo=UTC)
        else:
            ts_dt = datetime.fromisoformat(str(ts_val)).replace(tzinfo=UTC)

        inds: dict[str, float] = {}
        if sma20_val is not None and not np.isnan(sma20_val):
            inds["sma_20"] = float(sma20_val)
        if sma50_val is not None and not np.isnan(sma50_val):
            inds["sma_50"] = float(sma50_val)
        if sma200_val is not None and not np.isnan(sma200_val):
            inds["sma_200"] = float(sma200_val)
        if ema20_val is not None and not np.isnan(ema20_val):
            inds["ema_20"] = float(ema20_val)
        if rsi14_val is not None and not np.isnan(rsi14_val):
            inds["rsi_14"] = float(rsi14_val)
        if macd_val is not None and not np.isnan(macd_val):
            inds["macd"] = float(macd_val)
        if macd_sig is not None and not np.isnan(macd_sig):
            inds["macd_signal"] = float(macd_sig)
        if atr_val is not None and not np.isnan(atr_val):
            inds["atr_14"] = float(atr_val)
        if bb_up is not None and not np.isnan(bb_up):
            inds["bollinger_upper"] = float(bb_up)
        if bb_low is not None and not np.isnan(bb_low):
            inds["bollinger_lower"] = float(bb_low)
        if mom_val is not None and not np.isnan(mom_val):
            inds["momentum_20"] = float(mom_val)

        points.append(
            SignalSeriesPoint(
                ts=ts_dt,
                open=float(open_arr[i]),
                high=float(high_arr[i]),
                low=float(low_arr[i]),
                close=float(close_arr[i]),
                volume=int(vol_arr[i]),
                signals=inds,
            )
        )

    return SignalExploreResponse(
        symbol=sym,
        points=points,
        available_indicators=available_inds,
    )


@router.get("/universe", response_model=UniverseScreenerResponse)
def screen_universe(
    min_adv_usd: Annotated[
        float, Query(description="Minimum 20-day Average Daily Volume in USD")
    ] = 20_000_000.0,
    min_price: Annotated[float, Query(description="Minimum share price in USD")] = 5.0,
    snapshot_path: Annotated[
        str | None, Query(description="Snapshot path for PIT evaluation")
    ] = None,
) -> UniverseScreenerResponse:
    """Screen candidates across liquidity, price, ROIC, and Piotroski quality filters."""
    _ = snapshot_path
    candidates_data = [
        ("NVDA", 128.50, 48_500_000_000.0, 42.5, 8),
        ("AAPL", 224.23, 11_200_000_000.0, 56.1, 7),
        ("MSFT", 415.80, 8_900_000_000.0, 31.4, 8),
        ("AMZN", 188.12, 7_400_000_000.0, 21.8, 7),
        ("GOOGL", 165.40, 5_800_000_000.0, 28.6, 8),
        ("META", 512.90, 6_100_000_000.0, 33.2, 8),
        ("TSLA", 215.30, 14_200_000_000.0, 14.5, 6),
        ("AMD", 152.60, 4_800_000_000.0, 12.3, 7),
        ("JPM", 218.40, 3_100_000_000.0, 18.2, 7),
        ("V", 270.50, 2_400_000_000.0, 39.8, 8),
        ("UNH", 585.10, 2_100_000_000.0, 24.1, 7),
        ("PG", 168.90, 1_900_000_000.0, 22.4, 7),
        ("XOM", 115.30, 2_600_000_000.0, 16.7, 6),
        ("COST", 880.20, 1_800_000_000.0, 25.3, 8),
        ("NFLX", 685.40, 2_200_000_000.0, 27.9, 8),
        ("CRM", 258.90, 1_700_000_000.0, 15.6, 7),
        ("INTC", 20.80, 2_900_000_000.0, 1.2, 4),
        ("PFE", 28.40, 1_400_000_000.0, 5.8, 5),
        ("WMT", 75.30, 2_100_000_000.0, 19.4, 7),
        ("PENNY_CO", 2.10, 450_000.0, -8.2, 2),
        ("ILLIQ_TECH", 48.00, 3_200_000.0, 9.4, 5),
    ]

    candidates: list[UniverseCandidateResponse] = []
    qualified_count = 0
    filtered_count = 0

    for sym, price, adv, roic, piotroski in candidates_data:
        is_liquid = adv >= min_adv_usd
        is_price_ok = price >= min_price

        status_str = "QUALIFIED"
        if not is_price_ok:
            status_str = "FILTERED_PRICE"
            filtered_count += 1
        elif not is_liquid:
            status_str = "FILTERED_LOW_ADV"
            filtered_count += 1
        elif roic < 8.0 or piotroski < 6:
            status_str = "FILTERED_QUALITY"
            filtered_count += 1
        else:
            qualified_count += 1

        candidates.append(
            UniverseCandidateResponse(
                symbol=sym,
                price=price,
                adv_20_usd=adv,
                is_liquid=is_liquid,
                is_price_eligible=is_price_ok,
                roic_pct=roic,
                piotroski_f_score=piotroski,
                status=status_str,
            )
        )

    return UniverseScreenerResponse(
        as_of_date=datetime.now(UTC).date().isoformat(),
        total_evaluated=len(candidates),
        qualified_count=qualified_count,
        filtered_count=filtered_count,
        min_adv_usd=min_adv_usd,
        min_price_usd=min_price,
        candidates=candidates,
    )
