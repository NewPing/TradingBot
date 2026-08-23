"""FastAPI router for Signals Explorer and technical indicator inspection."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated

import numpy as np
from fastapi import APIRouter, Query

from atlas.api.schemas.signals import SignalExploreResponse, SignalSeriesPoint
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

        signals_dict: dict[str, float] = {}
        if sma20_val is not None:
            signals_dict["sma_20"] = round(sma20_val, 4)
        if sma50_val is not None:
            signals_dict["sma_50"] = round(sma50_val, 4)
        if sma200_val is not None:
            signals_dict["sma_200"] = round(sma200_val, 4)
        if ema20_val is not None:
            signals_dict["ema_20"] = round(ema20_val, 4)
        if rsi14_val is not None:
            signals_dict["rsi_14"] = round(rsi14_val, 4)
        if macd_val is not None:
            signals_dict["macd"] = round(macd_val, 4)
        if macd_sig is not None:
            signals_dict["macd_signal"] = round(macd_sig, 4)
        if atr_val is not None:
            signals_dict["atr_14"] = round(atr_val, 4)
        if bb_up is not None:
            signals_dict["bollinger_upper"] = round(bb_up, 4)
        if bb_low is not None:
            signals_dict["bollinger_lower"] = round(bb_low, 4)
        if mom_val is not None:
            signals_dict["momentum_20"] = round(mom_val, 4)

        points.append(
            SignalSeriesPoint(
                ts=ts_dt,
                open=float(open_arr[i]),
                high=float(high_arr[i]),
                low=float(low_arr[i]),
                close=float(close_arr[i]),
                volume=int(vol_arr[i]),
                signals=signals_dict,
            )
        )

    return SignalExploreResponse(
        symbol=sym,
        points=points,
        available_indicators=available_inds,
    )
