"""Comprehensive performance and risk metrics calculations."""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Any

import numpy as np
import numpy.typing as npt

from atlas.core.calendar import is_trading_day
from atlas.core.types import Fill


@dataclass(frozen=True, slots=True)
class PerformanceMetrics:
    """Comprehensive performance and risk metrics for a backtest run."""

    # Returns
    total_return: float
    cagr: float

    # Risk
    annualized_vol: float
    downside_vol: float
    max_drawdown: float
    avg_drawdown: float
    max_drawdown_days: int
    var_95: float
    cvar_95: float

    # Risk-adjusted
    sharpe_ratio: float
    sortino_ratio: float
    calmar_ratio: float

    # Trade stats
    total_trades: int
    winning_trades: int
    losing_trades: int
    win_rate: float
    profit_factor: float
    avg_trade_pnl: float
    max_consecutive_losses: int
    turnover: float
    exposure_pct: float

    # Frictional Costs & Holding Duration
    avg_holding_days: float = 0.0
    avg_win_holding_days: float = 0.0
    avg_loss_holding_days: float = 0.0
    total_slippage_usd: float = 0.0
    total_commissions_usd: float = 0.0
    total_fees_usd: float = 0.0
    total_frictional_drag_usd: float = 0.0
    gross_profit_usd: float = 0.0
    frictional_drag_pct: float = 0.0

    # Benchmark comparison
    benchmark_cagr: float | None = None
    alpha: float | None = None
    beta: float | None = None
    correlation: float | None = None
    information_ratio: float | None = None
    tracking_error: float | None = None


@dataclass(frozen=True, slots=True)
class HorizonMetrics:
    """Performance & S&P 500 benchmark metrics for a specific time horizon window."""

    horizon: str  # "10Y", "5Y", "3Y", "1Y", "YTD", "ALL"
    start_date: str
    end_date: str
    trading_days: int
    starting_capital: float
    ending_equity: float
    net_profit_usd: float
    strategy_return_pct: float
    strategy_cagr: float
    strategy_sharpe: float
    strategy_sortino: float
    strategy_max_drawdown: float
    strategy_calmar: float
    win_rate: float
    profit_factor: float
    total_trades: int

    # S&P 500 (SPY) Benchmark Comparison
    benchmark_starting_equity: float
    benchmark_ending_equity: float
    benchmark_profit_usd: float
    benchmark_return_pct: float
    benchmark_cagr: float
    benchmark_max_drawdown: float
    alpha: float
    beta: float
    information_ratio: float
    tracking_error: float
    correlation: float

    # Trade Durations & Costs
    avg_holding_days: float = 0.0
    avg_win_holding_days: float = 0.0
    avg_loss_holding_days: float = 0.0
    total_slippage_usd: float = 0.0
    total_commissions_usd: float = 0.0
    total_fees_usd: float = 0.0
    total_frictional_drag_usd: float = 0.0
    gross_profit_usd: float = 0.0
    frictional_drag_pct: float = 0.0


@dataclass(frozen=True, slots=True)
class MultiHorizonReport:
    """Consolidated multi-horizon evaluation report comparing strategy vs S&P 500 benchmark."""

    run_id: str
    horizons: list[HorizonMetrics]


def calculate_drawdown_series(
    equity_curve: npt.NDArray[np.float64],
) -> tuple[npt.NDArray[np.float64], float, float, int]:
    """Calculate drawdown series, max drawdown, average drawdown, and max drawdown duration in days."""
    if len(equity_curve) == 0:
        return np.array([], dtype=np.float64), 0.0, 0.0, 0

    peaks = np.maximum.accumulate(equity_curve)
    drawdowns = np.where(peaks > 0, (peaks - equity_curve) / peaks, 0.0)
    max_dd = float(np.max(drawdowns)) if len(drawdowns) > 0 else 0.0
    avg_dd = float(np.mean(drawdowns)) if len(drawdowns) > 0 else 0.0

    # Calculate max duration in days
    max_duration = 0
    current_duration = 0
    for dd in drawdowns:
        if dd > 1e-6:
            current_duration += 1
            if current_duration > max_duration:
                max_duration = current_duration
        else:
            current_duration = 0

    return drawdowns, max_dd, avg_dd, max_duration


def extract_roundtrip_trades(fills: list[Fill]) -> list[dict[str, Any]]:
    """Extract exact closed roundtrip trade records with dollar PnL and percentage returns using FIFO matching."""
    if not fills:
        return []

    # lot: (qty, price, ts, fees_total)
    long_lots: dict[str, list[list[Any]]] = {}
    short_lots: dict[str, list[list[Any]]] = {}
    completed_trades: list[dict[str, Any]] = []

    for f in fills:
        if f.symbol is not None:
            sym = str(f.symbol)
        else:
            parts = str(f.order_id).split("_")
            sym = parts[1] if len(parts) > 1 else "UNKNOWN"
        fill_price = float(f.price)
        total_fees = float(f.commission.amount + f.fees.amount)
        fill_qty = abs(f.qty)
        if f.side is not None:
            is_buy = (
                f.side.value.upper() == "BUY"
                if hasattr(f.side, "value")
                else str(f.side).upper() == "BUY"
            )
        else:
            is_buy = not (str(f.order_id).startswith("stop_") and "SELL" in str(f.venue)) and (
                f.qty > 0
            )

        fill_ts = (
            f.ts if isinstance(f.ts, datetime) else datetime.combine(f.ts, datetime.min.time())
        )

        if is_buy:
            # Match against existing short lots first (covering short)
            if sym in short_lots and short_lots[sym]:
                qty_needed = fill_qty
                while qty_needed > 0 and short_lots[sym]:
                    lot = short_lots[sym][0]
                    lot_qty, lot_price, lot_ts, lot_fees = lot[0], lot[1], lot[2], lot[3]
                    matched_qty = min(qty_needed, lot_qty)

                    fee_share = total_fees * (matched_qty / fill_qty) + lot_fees * (
                        matched_qty / lot_qty
                    )
                    trade_pnl = (lot_price - fill_price) * matched_qty - fee_share
                    cost_basis = lot_price * matched_qty
                    pnl_pct = trade_pnl / cost_basis if cost_basis > 0 else 0.0
                    duration_days = max(0, (fill_ts.date() - lot_ts.date()).days)

                    completed_trades.append(
                        {
                            "symbol": sym,
                            "pnl": trade_pnl,
                            "pnl_pct": pnl_pct,
                            "duration": duration_days,
                            "direction": "SHORT",
                            "entry_date": lot_ts.date() if isinstance(lot_ts, datetime) else lot_ts,
                            "exit_date": fill_ts.date()
                            if isinstance(fill_ts, datetime)
                            else fill_ts,
                        }
                    )

                    qty_needed -= matched_qty
                    if matched_qty == lot_qty:
                        short_lots[sym].pop(0)
                    else:
                        lot[0] -= matched_qty
                        lot[3] -= lot_fees * (matched_qty / lot_qty)

                if qty_needed > 0:
                    long_lots.setdefault(sym, []).append(
                        [qty_needed, fill_price, fill_ts, total_fees * (qty_needed / fill_qty)]
                    )
            else:
                long_lots.setdefault(sym, []).append([fill_qty, fill_price, fill_ts, total_fees])
        else:  # Sell
            # Match against existing long lots (closing long)
            if sym in long_lots and long_lots[sym]:
                qty_needed = fill_qty
                while qty_needed > 0 and long_lots[sym]:
                    lot = long_lots[sym][0]
                    lot_qty, lot_price, lot_ts, lot_fees = lot[0], lot[1], lot[2], lot[3]
                    matched_qty = min(qty_needed, lot_qty)

                    fee_share = total_fees * (matched_qty / fill_qty) + lot_fees * (
                        matched_qty / lot_qty
                    )
                    trade_pnl = (fill_price - lot_price) * matched_qty - fee_share
                    cost_basis = lot_price * matched_qty
                    pnl_pct = trade_pnl / cost_basis if cost_basis > 0 else 0.0
                    duration_days = max(0, (fill_ts.date() - lot_ts.date()).days)

                    completed_trades.append(
                        {
                            "symbol": sym,
                            "pnl": trade_pnl,
                            "pnl_pct": pnl_pct,
                            "duration": duration_days,
                            "direction": "LONG",
                            "entry_date": lot_ts.date() if isinstance(lot_ts, datetime) else lot_ts,
                            "exit_date": fill_ts.date()
                            if isinstance(fill_ts, datetime)
                            else fill_ts,
                        }
                    )

                    qty_needed -= matched_qty
                    if matched_qty == lot_qty:
                        long_lots[sym].pop(0)
                    else:
                        lot[0] -= matched_qty
                        lot[3] -= lot_fees * (matched_qty / lot_qty)

                if qty_needed > 0:
                    short_lots.setdefault(sym, []).append(
                        [qty_needed, fill_price, fill_ts, total_fees * (qty_needed / fill_qty)]
                    )
            else:
                short_lots.setdefault(sym, []).append([fill_qty, fill_price, fill_ts, total_fees])

    return completed_trades


def calculate_trade_statistics(
    fills: list[Fill],
    completed_trades: list[dict[str, Any]] | None = None,
) -> tuple[int, int, int, float, float, float, int, float, float, float]:
    """Calculate exact roundtrip trade statistics and holding durations from fill reports using FIFO matching."""
    if completed_trades is None:
        if not fills:
            return 0, 0, 0, 0.0, 0.0, 0.0, 0, 0.0, 0.0, 0.0
        completed_trades = extract_roundtrip_trades(fills)

    total_trades = len(completed_trades)
    if total_trades == 0:
        return 0, 0, 0, 0.0, 0.0, 0.0, 0, 0.0, 0.0, 0.0

    wins = [t for t in completed_trades if t["pnl"] > 0]
    losses = [t for t in completed_trades if t["pnl"] <= 0]

    winning = len(wins)
    losing = len(losses)
    win_rate = winning / total_trades if total_trades > 0 else 0.0

    gross_win = sum(t["pnl"] for t in wins)
    gross_loss = abs(sum(t["pnl"] for t in losses))
    if gross_loss > 0:
        profit_factor = gross_win / gross_loss
    elif gross_win > 0:
        profit_factor = 999.99
    else:
        profit_factor = 0.0
    avg_pnl = sum(t["pnl"] for t in completed_trades) / total_trades

    # Max consecutive losses
    max_consec_losses = 0
    curr_consec = 0
    for t in completed_trades:
        if t["pnl"] <= 0:
            curr_consec += 1
            if curr_consec > max_consec_losses:
                max_consec_losses = curr_consec
        else:
            curr_consec = 0

    avg_hold = float(np.mean([t["duration"] for t in completed_trades]))
    avg_win_hold = float(np.mean([t["duration"] for t in wins])) if wins else 0.0
    avg_loss_hold = float(np.mean([t["duration"] for t in losses])) if losses else 0.0

    return (
        total_trades,
        winning,
        losing,
        round(win_rate, 4),
        round(profit_factor, 2),
        round(avg_pnl, 2),
        max_consec_losses,
        round(avg_hold, 1),
        round(avg_win_hold, 1),
        round(avg_loss_hold, 1),
    )


def compute_metrics(
    equity_series: list[float],
    initial_capital: float,
    fills: list[Fill] | None = None,
    benchmark_equity: list[float] | None = None,
    risk_free_rate: float = 0.0,
    annual_days: float = 252.0,
    completed_trades: list[dict[str, Any]] | None = None,
    timestamps: Sequence[datetime | date | str] | None = None,
) -> PerformanceMetrics:
    """Compute complete PerformanceMetrics from daily equity curve and fill history."""
    fills = fills or []
    if len(equity_series) < 2:
        return PerformanceMetrics(
            total_return=0.0,
            cagr=0.0,
            annualized_vol=0.0,
            downside_vol=0.0,
            max_drawdown=0.0,
            avg_drawdown=0.0,
            max_drawdown_days=0,
            var_95=0.0,
            cvar_95=0.0,
            sharpe_ratio=0.0,
            sortino_ratio=0.0,
            calmar_ratio=0.0,
            total_trades=0,
            winning_trades=0,
            losing_trades=0,
            win_rate=0.0,
            profit_factor=0.0,
            avg_trade_pnl=0.0,
            max_consecutive_losses=0,
            turnover=0.0,
            exposure_pct=0.0,
        )

    eq_arr = np.array(equity_series, dtype=np.float64)
    start_val = float(eq_arr[0]) if eq_arr[0] > 0 else initial_capital
    end_val = float(eq_arr[-1])

    total_return = (end_val - start_val) / start_val if start_val > 0 else 0.0
    num_days = len(eq_arr) - 1
    years = max(1.0 / annual_days, num_days / annual_days)

    if end_val > 0 and start_val > 0:
        cagr = float((end_val / start_val) ** (1.0 / years) - 1.0)
    else:
        cagr = -1.0

    # Daily returns
    daily_returns = np.diff(eq_arr) / eq_arr[:-1]
    daily_returns = np.nan_to_num(daily_returns, nan=0.0, posinf=0.0, neginf=0.0)

    # Volatilities & Expected Return
    mean_daily_ret = float(np.mean(daily_returns)) if len(daily_returns) > 0 else 0.0
    daily_rf = risk_free_rate / annual_days
    excess_daily = mean_daily_ret - daily_rf

    daily_vol = float(np.std(daily_returns, ddof=1)) if len(daily_returns) > 1 else 0.0
    ann_vol = daily_vol * math.sqrt(annual_days)

    # Downside Semi-Deviation for Sortino (Root Mean Square of sub-target returns)
    downside_diff = np.minimum(0.0, daily_returns - daily_rf)
    downside_variance = float(np.mean(downside_diff**2)) if len(downside_diff) > 0 else 0.0
    ann_downside_vol = math.sqrt(downside_variance) * math.sqrt(annual_days)

    # Drawdowns
    _, max_dd, avg_dd, max_dd_days = calculate_drawdown_series(eq_arr)

    # Value at Risk / CVaR 95%
    var_95 = float(np.percentile(daily_returns, 5)) if len(daily_returns) > 0 else 0.0
    worst_5pct = daily_returns[daily_returns <= var_95]
    cvar_95 = float(np.mean(worst_5pct)) if len(worst_5pct) > 0 else var_95

    # Ratios
    sharpe = (excess_daily * math.sqrt(annual_days)) / daily_vol if daily_vol > 1e-6 else 0.0
    sortino = (excess_daily * annual_days) / ann_downside_vol if ann_downside_vol > 1e-6 else 0.0
    calmar = (cagr / max_dd) if max_dd > 1e-6 else (999.99 if cagr > 0 else 0.0)

    # Trade stats & holding durations via true FIFO roundtrip lot matching
    (
        n_trades,
        n_win,
        n_loss,
        win_rate,
        profit_factor,
        avg_pnl,
        max_consec,
        avg_hold,
        avg_win_hold,
        avg_loss_hold,
    ) = calculate_trade_statistics(fills, completed_trades=completed_trades)

    # Trades, costs, and exposure
    total_trades = n_trades

    # Market exposure based on union of active holding dates across all positions
    if fills and len(equity_series) > 0:
        active_dates: set[date] = set()
        # Sort fills chronologically to reconstruct active date intervals
        sorted_fills = sorted(
            fills,
            key=lambda f: (
                f.ts if isinstance(f.ts, datetime) else datetime.combine(f.ts, datetime.min.time())
            ),
        )
        # Track position lots: sym -> list of open dates
        open_lot_dates: dict[str, list[tuple[date, int]]] = {}
        for f in sorted_fills:
            f_sym = str(f.symbol) if f.symbol else "UNKNOWN"
            f_date = f.ts.date() if isinstance(f.ts, datetime) else f.ts
            f_qty = abs(f.qty)

            # Match against existing open lots
            existing_lots = open_lot_dates.get(f_sym, [])
            if existing_lots:
                # Lot closed/reduced: record active date span
                needed = f_qty
                while needed > 0 and existing_lots:
                    entry_d, lot_q = existing_lots[0]
                    matched = min(needed, lot_q)
                    # Add all trading session dates in interval [entry_d, f_date]
                    curr_d = entry_d
                    while curr_d <= f_date:
                        if is_trading_day(curr_d):
                            active_dates.add(curr_d)
                        curr_d = curr_d + timedelta(days=1)
                    needed -= matched
                    if matched == lot_q:
                        existing_lots.pop(0)
                    else:
                        existing_lots[0] = (entry_d, lot_q - matched)
                if needed > 0:
                    existing_lots.append((f_date, needed))
            else:
                existing_lots.append((f_date, f_qty))
            open_lot_dates[f_sym] = existing_lots

        # Any remaining open lots that were never closed
        last_date: date
        if timestamps:
            first_ts = timestamps[-1]
            if isinstance(first_ts, datetime):
                last_date = first_ts.date()
            elif isinstance(first_ts, date):
                last_date = first_ts
            else:
                last_date = date.fromisoformat(str(first_ts).split("T")[0])
        else:
            last_date = (
                sorted_fills[-1].ts.date()
                if isinstance(sorted_fills[-1].ts, datetime)
                else sorted_fills[-1].ts
            )

        for _sym_str, rem_lots in open_lot_dates.items():
            for entry_d, _ in rem_lots:
                curr_d = entry_d
                while curr_d <= last_date:
                    if is_trading_day(curr_d):
                        active_dates.add(curr_d)
                    curr_d = curr_d + timedelta(days=1)

        total_days = max(1, len(equity_series))
        exposure_pct = min(1.0, max(0.0, len(active_dates) / float(total_days)))
    else:
        exposure_pct = 0.0

    total_fill_notional = sum(float(f.qty * f.price) for f in fills)
    avg_equity = float(np.mean(eq_arr))
    # Annualized portfolio turnover: (Total Notional Traded / 2) / (Avg Equity * Years)
    turnover = (
        ((total_fill_notional / 2.0) / (avg_equity * years))
        if (avg_equity > 0 and years > 0)
        else 0.0
    )

    # Frictional costs
    tot_slip = sum(float(f.slippage_est.amount) for f in fills)
    tot_comm = sum(float(f.commission.amount) for f in fills)
    tot_fees = sum(float(f.fees.amount) for f in fills)
    tot_frict = tot_slip + tot_comm + tot_fees
    net_pnl = end_val - start_val
    gross_pnl = net_pnl + tot_frict
    frict_pct = (
        (tot_frict / gross_pnl * 100.0)
        if gross_pnl > 0
        else ((tot_frict / initial_capital * 100.0) if initial_capital > 0 else 0.0)
    )

    # Benchmark stats if provided
    bm_cagr = None
    alpha = None
    beta = None
    corr = None
    info_ratio = None
    track_err = None

    if benchmark_equity is not None and len(benchmark_equity) == len(equity_series):
        bm_arr = np.array(benchmark_equity, dtype=np.float64)
        bm_start = float(bm_arr[0]) if bm_arr[0] > 0 else 1.0
        bm_end = float(bm_arr[-1])
        bm_cagr = (
            float((bm_end / bm_start) ** (1.0 / years) - 1.0)
            if bm_end > 0 and bm_start > 0
            else 0.0
        )

        bm_returns = np.diff(bm_arr) / bm_arr[:-1]
        bm_returns = np.nan_to_num(bm_returns, nan=0.0, posinf=0.0, neginf=0.0)

        if len(daily_returns) > 1 and np.std(bm_returns) > 1e-6:
            cov_matrix = np.cov(daily_returns, bm_returns)
            cov_val = float(cov_matrix[0, 1])
            var_bm = float(cov_matrix[1, 1])
            beta = float(cov_val / var_bm) if var_bm > 1e-6 else 1.0
            corr = float(np.corrcoef(daily_returns, bm_returns)[0, 1])
            bm_mean_ret = float(np.mean(bm_returns))
            alpha = float(
                (mean_daily_ret * annual_days - risk_free_rate)
                - beta * (bm_mean_ret * annual_days - risk_free_rate)
            )

            active_returns = daily_returns - bm_returns
            track_err = float(np.std(active_returns, ddof=1)) * math.sqrt(annual_days)
            active_mean_annualized = (mean_daily_ret - bm_mean_ret) * annual_days
            info_ratio = float(active_mean_annualized / track_err) if track_err > 1e-6 else 0.0

    return PerformanceMetrics(
        total_return=total_return,
        cagr=cagr,
        annualized_vol=ann_vol,
        downside_vol=ann_downside_vol,
        max_drawdown=max_dd,
        avg_drawdown=avg_dd,
        max_drawdown_days=max_dd_days,
        var_95=var_95,
        cvar_95=cvar_95,
        sharpe_ratio=sharpe,
        sortino_ratio=sortino,
        calmar_ratio=calmar,
        total_trades=total_trades,
        winning_trades=n_win,
        losing_trades=n_loss,
        win_rate=win_rate,
        profit_factor=profit_factor,
        avg_trade_pnl=avg_pnl,
        max_consecutive_losses=max_consec,
        turnover=turnover,
        exposure_pct=exposure_pct,
        avg_holding_days=avg_hold,
        avg_win_holding_days=avg_win_hold,
        avg_loss_holding_days=avg_loss_hold,
        total_slippage_usd=tot_slip,
        total_commissions_usd=tot_comm,
        total_fees_usd=tot_fees,
        total_frictional_drag_usd=tot_frict,
        gross_profit_usd=gross_pnl,
        frictional_drag_pct=frict_pct,
        benchmark_cagr=bm_cagr,
        alpha=alpha,
        beta=beta,
        correlation=corr,
        information_ratio=info_ratio,
        tracking_error=track_err,
    )


def compute_multi_horizon_metrics(
    timestamps: Sequence[datetime | date | str],
    equity_series: list[float],
    initial_capital: float,
    benchmark_equity: list[float] | None = None,
    fills: list[Fill] | None = None,
    risk_free_rate: float = 0.0,
    annual_days: float = 252.0,
) -> list[HorizonMetrics]:
    """
    Compute multi-horizon performance comparison matrices (10Y, 5Y, 3Y, 1Y, YTD, ALL)
    aligned against S&P 500 (SPY) benchmark index.
    """
    fills = fills or []
    if not equity_series or len(equity_series) < 2 or not timestamps:
        return []

    # Parse timestamps into date objects
    parsed_dates: list[date] = []
    for ts in timestamps:
        if isinstance(ts, datetime):
            parsed_dates.append(ts.date())
        elif isinstance(ts, date):
            parsed_dates.append(ts)
        else:
            parsed_dates.append(date.fromisoformat(str(ts).split("T")[0]))

    total_len = len(equity_series)
    end_date = parsed_dates[-1]

    # Benchmark series normalization if provided
    has_benchmark = bool(benchmark_equity and len(benchmark_equity) == total_len)
    bm_series: list[float] = (
        list(benchmark_equity) if (benchmark_equity is not None and has_benchmark) else []
    )

    horizon_definitions: list[tuple[str, int | str]] = [
        ("10Y", 2520),
        ("5Y", 1260),
        ("3Y", 756),
        ("1Y", 252),
        ("YTD", "YTD"),
        ("ALL", "ALL"),
    ]

    results: list[HorizonMetrics] = []
    all_completed_trades = extract_roundtrip_trades(fills)

    for label, rule in horizon_definitions:
        start_idx = 0
        if rule == "ALL":
            start_idx = 0
        elif rule == "YTD":
            ytd_year = end_date.year
            for idx, d in enumerate(parsed_dates):
                if d.year == ytd_year:
                    start_idx = idx
                    break
        elif isinstance(rule, int):
            start_idx = total_len - rule if total_len > rule else 0

        sub_dates = parsed_dates[start_idx:]
        sub_equity = equity_series[start_idx:]
        sub_bm = bm_series[start_idx:] if has_benchmark else None
        trading_days = len(sub_equity)

        if trading_days < 2:
            continue

        start_cap = sub_equity[0] if sub_equity[0] > 0 else initial_capital
        end_cap = sub_equity[-1]
        net_profit = end_cap - start_cap
        strat_return_pct = (net_profit / start_cap) if start_cap > 0 else 0.0

        years = max(1.0 / annual_days, (trading_days - 1) / annual_days)
        strat_cagr = (
            float((end_cap / start_cap) ** (1.0 / years) - 1.0)
            if start_cap > 0 and end_cap > 0
            else 0.0
        )

        # Sub-fills within date range
        start_dt = sub_dates[0]
        end_dt = sub_dates[-1]
        sub_fills = [
            f
            for f in fills
            if start_dt <= (f.ts.date() if isinstance(f.ts, datetime) else f.ts) <= end_dt
        ]
        sub_completed_trades = [
            t
            for t in all_completed_trades
            if t.get("exit_date") is not None and start_dt <= t["exit_date"] <= end_dt
        ]

        sub_metrics = compute_metrics(
            equity_series=sub_equity,
            initial_capital=start_cap,
            fills=sub_fills,
            benchmark_equity=sub_bm,
            risk_free_rate=risk_free_rate,
            annual_days=annual_days,
            completed_trades=sub_completed_trades,
            timestamps=sub_dates,
        )

        if sub_bm is not None:
            bm_start_cap = sub_bm[0]
            bm_end_cap = sub_bm[-1]
            bm_profit = bm_end_cap - bm_start_cap
            bm_return_pct = (bm_profit / bm_start_cap) if bm_start_cap > 0 else 0.0
            bm_cagr = (
                float((bm_end_cap / bm_start_cap) ** (1.0 / years) - 1.0)
                if bm_start_cap > 0 and bm_end_cap > 0
                else 0.0
            )
            _, bm_max_dd, _, _ = calculate_drawdown_series(np.array(sub_bm, dtype=np.float64))
        else:
            bm_start_cap = round(start_cap, 2)
            bm_end_cap = round(start_cap, 2)
            bm_profit = 0.0
            bm_return_pct = 0.0
            bm_cagr = 0.0
            bm_max_dd = 0.0

        results.append(
            HorizonMetrics(
                horizon=label,
                start_date=start_dt.isoformat(),
                end_date=end_dt.isoformat(),
                trading_days=trading_days,
                starting_capital=round(start_cap, 2),
                ending_equity=round(end_cap, 2),
                net_profit_usd=round(net_profit, 2),
                strategy_return_pct=round(strat_return_pct, 4),
                strategy_cagr=round(strat_cagr, 4),
                strategy_sharpe=round(sub_metrics.sharpe_ratio, 2),
                strategy_sortino=round(sub_metrics.sortino_ratio, 2),
                strategy_max_drawdown=round(sub_metrics.max_drawdown, 4),
                strategy_calmar=round(sub_metrics.calmar_ratio, 2),
                win_rate=round(sub_metrics.win_rate, 4),
                profit_factor=round(sub_metrics.profit_factor, 2),
                total_trades=sub_metrics.total_trades,
                benchmark_starting_equity=round(bm_start_cap, 2),
                benchmark_ending_equity=round(bm_end_cap, 2),
                benchmark_profit_usd=round(bm_profit, 2),
                benchmark_return_pct=round(bm_return_pct, 4),
                benchmark_cagr=round(bm_cagr, 4),
                benchmark_max_drawdown=round(bm_max_dd, 4),
                alpha=round(sub_metrics.alpha, 4) if sub_metrics.alpha is not None else 0.0,
                beta=round(sub_metrics.beta, 2)
                if sub_metrics.beta is not None
                else (1.0 if has_benchmark else 0.0),
                information_ratio=round(sub_metrics.information_ratio, 2)
                if sub_metrics.information_ratio is not None
                else 0.0,
                tracking_error=round(
                    sub_metrics.tracking_error if sub_metrics.tracking_error is not None else 0.0,
                    4,
                ),
                correlation=round(sub_metrics.correlation, 2)
                if sub_metrics.correlation is not None
                else 0.0,
                avg_holding_days=round(sub_metrics.avg_holding_days, 1),
                avg_win_holding_days=round(sub_metrics.avg_win_holding_days, 1),
                avg_loss_holding_days=round(sub_metrics.avg_loss_holding_days, 1),
                total_slippage_usd=round(sub_metrics.total_slippage_usd, 2),
                total_commissions_usd=round(sub_metrics.total_commissions_usd, 2),
                total_fees_usd=round(sub_metrics.total_fees_usd, 2),
                total_frictional_drag_usd=round(sub_metrics.total_frictional_drag_usd, 2),
                gross_profit_usd=round(sub_metrics.gross_profit_usd, 2),
                frictional_drag_pct=round(sub_metrics.frictional_drag_pct, 2),
            )
        )

    return results
