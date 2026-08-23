"""ATLAS comprehensive database seeding script for market data, backtest runs, live paper state, fundamentals, narrative, and taxes."""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from pathlib import Path
import numpy as np
import polars as pl
from sqlalchemy import create_engine, select, delete
from sqlalchemy.orm import Session

from atlas.backtest.engine import BacktestEngine
from atlas.backtest.metrics import compute_multi_horizon_metrics
from atlas.backtest.registry import RunRegistry
from atlas.core.config import get_settings
from atlas.core.money import Money
from atlas.core.types import Bar, Fill, Side, Symbol
from atlas.data.models import (
    Base,
    Bar1D,
    CorporateAction,
    EarningsEvent,
    ECBExchangeRate,
    FillRecord,
    FundamentalFiling,
    Instrument,
    NewsArticle,
    NewsScore,
    OrderRecord,
    PromptTemplate,
    ResearchHypothesis,
    ResearchReport,
    ResearchSweep,
    Run,
    EquityPoint,
    RunMetric,
    RunTrade,
    ShadowExecutionLog,
    StrategyVersion,
    TaxEvent,
    TaxLot,
    Trial,
    UniverseSnapshot,
)
from atlas.data.snapshots import SnapshotManager
from atlas.research.sweep import build_research_dataset
from atlas.strategies.registry import StrategyVersionRegistry
from atlas.strategies.spec import StrategySpec

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("seed")


def seed_all() -> None:
    settings = get_settings()
    engine = create_engine(settings.atlas_db_url)
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        # 1. Sync strategy YAML specifications
        logger.info("1. Syncing strategy YAML specs...")
        spec_reg = StrategyVersionRegistry(session)
        spec_reg.sync_directory(Path("strategies"))

        # 2. Seed Instruments
        logger.info("2. Seeding instruments...")
        instruments_data = [
            ("SPY", "SPDR S&P 500 ETF Trust", "NYSE ARCA", "Index ETF", "Large Cap Blend", True, Decimal("42000000000.00")),
            ("QQQ", "Invesco QQQ Trust", "NASDAQ", "Index ETF", "Tech Large Cap", True, Decimal("21000000000.00")),
            ("AAPL", "Apple Inc.", "NASDAQ", "Technology", "Consumer Electronics", False, Decimal("11500000000.00")),
            ("MSFT", "Microsoft Corporation", "NASDAQ", "Technology", "Software—Infrastructure", False, Decimal("9800000000.00")),
            ("NVDA", "NVIDIA Corporation", "NASDAQ", "Technology", "Semiconductors", False, Decimal("18500000000.00")),
            ("AMZN", "Amazon.com Inc.", "NASDAQ", "Consumer Cyclical", "Internet Retail", False, Decimal("7400000000.00")),
            ("GOOGL", "Alphabet Inc.", "NASDAQ", "Communication Services", "Internet Content & Info", False, Decimal("5600000000.00")),
            ("META", "Meta Platforms Inc.", "NASDAQ", "Communication Services", "Internet Content & Info", False, Decimal("6200000000.00")),
            ("TSLA", "Tesla Inc.", "NASDAQ", "Consumer Cyclical", "Auto Manufacturers", False, Decimal("14200000000.00")),
            ("AGG", "iShares Core U.S. Aggregate Bond ETF", "NYSE ARCA", "Fixed Income", "Total Bond Market", True, Decimal("1800000000.00")),
        ]
        for sym, name, exch, sec, ind, is_etf, adv in instruments_data:
            existing = session.scalar(select(Instrument).where(Instrument.symbol == sym))
            if not existing:
                session.add(
                    Instrument(
                        symbol=sym,
                        name=name,
                        exchange=exch,
                        sector=sec,
                        industry=ind,
                        listed_on=date(2005, 1, 1),
                        is_etf=is_etf,
                        adv_usd=adv,
                    )
                )
        session.commit()

        # 3. Ingest Market Data (bars_1d) & Parquet Snapshot
        logger.info("3. Generating market dataset and deterministic snapshot...")
        symbols = [Symbol(s[0]) for s in instruments_data]
        start_d = date(2015, 1, 1)
        end_d = date(2024, 12, 31)
        dataset_df = build_research_dataset(symbols=symbols, start_d=start_d, end_d=end_d, seed=1337)

        bar_count = session.query(Bar1D).count()
        if bar_count == 0:
            bars_to_insert = []
            for row in dataset_df.iter_rows(named=True):
                bars_to_insert.append(
                    Bar1D(
                        symbol=row["symbol"],
                        ts=row["ts"],
                        open=Decimal(str(row["open"])),
                        high=Decimal(str(row["high"])),
                        low=Decimal(str(row["low"])),
                        close=Decimal(str(row["close"])),
                        volume=int(row["volume"]),
                        adj_factor=Decimal(str(row.get("adj_factor", 1.0))),
                        source="sim_gbm_v1",
                    )
                )

            logger.info("Inserting %d bars into bars_1d table...", len(bars_to_insert))
            session.bulk_save_objects(bars_to_insert)
            session.commit()
        else:
            logger.info("bars_1d table already contains %d bars, keeping...", bar_count)

        # Save snapshot
        snap_dir = Path("data/snapshots")
        snap_dir.mkdir(parents=True, exist_ok=True)
        snap_manager = SnapshotManager(base_dir=snap_dir)
        snapshots = list(snap_dir.glob("snapshot_*"))
        if not snapshots:
            bars_for_snap = [
                Bar(
                    symbol=Symbol(r["symbol"]),
                    ts=r["ts"],
                    open=Decimal(str(r["open"])),
                    high=Decimal(str(r["high"])),
                    low=Decimal(str(r["low"])),
                    close=Decimal(str(r["close"])),
                    volume=int(r["volume"]),
                    adj_factor=Decimal(str(r.get("adj_factor", 1.0))),
                    vwap=Decimal(str(r.get("close"))),
                    source="sim_gbm_v1",
                )
                for r in dataset_df.iter_rows(named=True)
            ]
            meta = snap_manager.create_snapshot(snapshot_date=end_d, bars=bars_for_snap)
            snap_id = meta.snapshot_id
            logger.info("Snapshot created: %s (%d bars)", meta.snapshot_id, meta.bars_count)
        else:
            snap_id = sorted(snapshots)[-1].name
            logger.info("Using existing snapshot: %s", snap_id)

        # 4. Execute Backtests & Store Baseline Runs
        logger.info("4. Executing backtests across strategy generations...")
        run_reg = RunRegistry(session)
        strategy_specs_to_run = [
            ("core_trend_1.0.0", "strategies/core_trend_v1.yaml"),
            ("core_trend_l2", "strategies/core_trend_l2.yaml"),
            ("core_trend_l3", "strategies/core_trend_l3.yaml"),
            ("core_narrative_l4", "strategies/core_narrative_l4.yaml"),
            ("core_catalyst_ai_v5", "strategies/core_catalyst_ai_v5.yaml"),
            ("swing_meanrev_v1", "strategies/swing_meanrev_v1.yaml"),
            ("benchmarks_1.0.0", "strategies/benchmarks_60_40.yaml"),
        ]

        for ver_id, spec_file in strategy_specs_to_run:
            if not Path(spec_file).exists():
                logger.warning("Spec file %s not found, skipping", spec_file)
                continue

            spec = StrategySpec.from_yaml(spec_file)
            ver_rec = spec_reg.get_or_raise(ver_id)
            run_id = f"run_{spec.name}_{spec.version.replace('.', '_')}"

            # Check if already recorded
            existing_run = session.scalar(select(Run).where(Run.id == run_id))
            if existing_run:
                logger.info("Run %s already exists, skipping...", run_id)
                continue

            logger.info("Running backtest for %s (%s)...", ver_id, spec.name)
            engine_inst = BacktestEngine(spec=spec, data=dataset_df, initial_capital=Money(Decimal("100000.00"), "USD"))
            res = engine_inst.run(start_date=date(2019, 1, 1), end_date=date(2022, 12, 31), benchmark_symbol=Symbol("SPY"))

            # Metrics
            m_dict = {
                "total_return": res.metrics.total_return,
                "cagr": res.metrics.cagr,
                "annualized_vol": res.metrics.annualized_vol,
                "downside_vol": res.metrics.downside_vol,
                "max_drawdown": res.metrics.max_drawdown,
                "max_drawdown_days": res.metrics.max_drawdown_days,
                "sharpe": res.metrics.sharpe_ratio,
                "sortino": res.metrics.sortino_ratio,
                "calmar": res.metrics.calmar_ratio,
                "win_rate": res.metrics.win_rate,
                "profit_factor": res.metrics.profit_factor,
                "turnover": res.metrics.turnover,
                "exposure_pct": res.metrics.exposure_pct,
                "benchmark_cagr": res.metrics.benchmark_cagr,
                "alpha": res.metrics.alpha,
                "beta": res.metrics.beta,
                "correlation": res.metrics.correlation,
            }

            # Equity curve
            eq_curve = []
            peak_eq = 0.0
            for pt in res.equity_curve:
                eq_val = float(str(pt.equity.amount)) if hasattr(pt.equity, "amount") else float(pt.equity)
                cash_val = float(str(pt.cash.amount)) if hasattr(pt.cash, "amount") else float(pt.cash)
                if eq_val > peak_eq:
                    peak_eq = eq_val
                dd = (peak_eq - eq_val) / peak_eq if peak_eq > 0 else 0.0
                eq_curve.append({
                    "ts": pt.ts,
                    "total_equity": eq_val,
                    "cash": cash_val,
                    "drawdown": dd,
                    "per_bucket": {spec.bucket.value: eq_val},
                })

            # Trades from fills (FIFO lot matching)
            trades_list = []
            trade_counter = 1
            long_lots = {}
            for f in res.fills:
                sym_str = str(f.symbol) if f.symbol else "SPY"
                fill_px = float(f.price)
                fill_q = abs(f.qty)
                is_buy = f.side == Side.BUY if f.side is not None else (f.qty > 0)

                if is_buy:
                    long_lots.setdefault(sym_str, []).append({
                        "qty": fill_q,
                        "price": fill_px,
                        "ts": f.ts,
                        "fees": float(f.commission.amount + f.fees.amount),
                    })
                else:
                    if sym_str in long_lots and long_lots[sym_str]:
                        lot = long_lots[sym_str].pop(0)
                        pnl = (fill_px - lot["price"]) * min(fill_q, lot["qty"])
                        ret = (fill_px - lot["price"]) / lot["price"] if lot["price"] > 0 else 0.0
                        trades_list.append({
                            "trade_id": f"T{trade_counter:04d}",
                            "symbol": sym_str,
                            "direction": "LONG",
                            "entry_time": lot["ts"],
                            "exit_time": f.ts,
                            "entry_price": lot["price"],
                            "exit_price": fill_px,
                            "quantity": min(fill_q, lot["qty"]),
                            "pnl": round(pnl, 2),
                            "pnl_net": round(pnl - 2.0, 2),
                            "return_pct": round(ret, 4),
                            "fees": 2.0,
                            "slippage": 1.5,
                            "exit_reason": "SIGNAL",
                        })
                        trade_counter += 1

            run_id = f"run_{spec.name}_{spec.version.replace('.', '_')}"
            run_rec = run_reg.record_run(
                run_id=run_id,
                strategy_version_id=ver_id,
                mode="BACKTEST",
                start_ts=datetime.combine(res.start_date, datetime.min.time(), tzinfo=UTC),
                end_ts=datetime.combine(res.end_date, datetime.max.time(), tzinfo=UTC),
                data_snapshot_id=snap_id,
                spec_hash=ver_rec.spec_hash,
                cost_model_hash=spec.costs.model,
                seed=42,
                summary_metrics=m_dict,
                equity_curve=eq_curve,
                trades=trades_list,
                status="COMPLETED",
            )
            logger.info("Recorded run %s (CAGR=%.1f%%, Sharpe=%.2f, Trades=%d)", run_id, m_dict["cagr"] * 100, m_dict["sharpe"], len(trades_list))

        # 5. Seed Live / Paper Trading State & Orders / Fills
        logger.info("5. Seeding Live/Paper trading orders, fills, and shadow logs...")
        session.execute(delete(FillRecord))
        session.execute(delete(OrderRecord))
        session.execute(delete(ShadowExecutionLog))
        session.commit()

        sample_orders = [
            ("ord_001", "run_core_catalyst_ai_v5_5_0_0", "core_catalyst_ai_v5", "CORE", "NVDA", "BUY", 150, "LIMIT", Decimal("124.50"), Decimal("118.00"), "FILLED"),
            ("ord_002", "run_core_catalyst_ai_v5_5_0_0", "core_catalyst_ai_v5", "CORE", "MSFT", "BUY", 80, "LIMIT", Decimal("442.00"), Decimal("425.00"), "FILLED"),
            ("ord_003", "run_core_catalyst_ai_v5_5_0_0", "core_catalyst_ai_v5", "CORE", "AAPL", "BUY", 120, "MARKET", None, Decimal("215.00"), "FILLED"),
            ("ord_004", "run_swing_meanrev_l2_2_0_0", "swing_meanrev_l2", "SWING", "TSLA", "BUY", 100, "LIMIT", Decimal("228.00"), Decimal("215.00"), "SUBMITTED"),
            ("ord_005", "run_swing_meanrev_l2_2_0_0", "swing_meanrev_l2", "SWING", "AMZN", "BUY", 90, "LIMIT", Decimal("176.50"), Decimal("169.00"), "SUBMITTED"),
        ]

        for ord_id, r_id, v_id, b_id, sym, side, qty, o_type, l_px, s_px, stat in sample_orders:
            session.add(
                OrderRecord(
                    id=ord_id,
                    run_id=r_id,
                    strategy_version_id=v_id,
                    bucket=b_id,
                    symbol=sym,
                    side=side,
                    qty=qty,
                    order_type=o_type,
                    tif="DAY",
                    limit_px=l_px,
                    stop_px=s_px,
                    status=stat,
                    created_ts=datetime.now(UTC) - timedelta(minutes=np.random.randint(5, 120)),
                )
            )

        session.commit()

        # Fills
        sample_fills = [
            ("ord_001", datetime.now(UTC) - timedelta(minutes=45), 150, Decimal("124.45"), Decimal("0.00"), Decimal("0.32"), Decimal("0.02"), "ALPACA_PAPER"),
            ("ord_002", datetime.now(UTC) - timedelta(minutes=40), 80, Decimal("441.95"), Decimal("0.00"), Decimal("0.71"), Decimal("0.03"), "ALPACA_PAPER"),
            ("ord_003", datetime.now(UTC) - timedelta(minutes=30), 120, Decimal("223.10"), Decimal("0.00"), Decimal("0.54"), Decimal("0.02"), "ALPACA_PAPER"),
        ]
        for o_id, ts, qty, px, comm, fees, slip, ven in sample_fills:
            session.add(
                FillRecord(
                    order_id=o_id,
                    ts=ts,
                    qty=qty,
                    price=px,
                    commission=comm,
                    fees=fees,
                    slippage_est=slip,
                    venue=ven,
                )
            )

        # Shadow Execution Logs
        shadow_records = [
            ("shadow_001", "run_core_catalyst_ai_v5_5_0_0", "NVDA", datetime.now(UTC) - timedelta(minutes=45), "BUY", 150, Decimal("124.40"), Decimal("124.45"), Decimal("4.02"), Decimal("8.40"), "IBKR_SMART"),
            ("shadow_002", "run_core_catalyst_ai_v5_5_0_0", "MSFT", datetime.now(UTC) - timedelta(minutes=40), "BUY", 80, Decimal("442.00"), Decimal("441.95"), Decimal("-1.13"), Decimal("12.10"), "IBKR_SMART"),
            ("shadow_003", "run_core_catalyst_ai_v5_5_0_0", "AAPL", datetime.now(UTC) - timedelta(minutes=30), "BUY", 120, Decimal("223.00"), Decimal("223.10"), Decimal("4.48"), Decimal("10.70"), "IBKR_SMART"),
            ("shadow_004", "run_core_narrative_l4_4_0_0", "GOOGL", datetime.now(UTC) - timedelta(hours=2), "BUY", 110, Decimal("165.20"), Decimal("165.22"), Decimal("1.21"), Decimal("14.30"), "IBKR_SMART"),
            ("shadow_005", "run_core_narrative_l4_4_0_0", "META", datetime.now(UTC) - timedelta(hours=3), "BUY", 65, Decimal("495.00"), Decimal("494.90"), Decimal("-2.02"), Decimal("11.20"), "IBKR_SMART"),
        ]
        for s_id, r_id, sym, ts, side, qty, m_px, s_px, slip_bps, lat_ms, ven in shadow_records:
            session.add(
                ShadowExecutionLog(
                    id=s_id,
                    run_id=r_id,
                    symbol=sym,
                    timestamp=ts,
                    side=side,
                    quantity=qty,
                    model_price_usd=m_px,
                    simulated_fill_price_usd=s_px,
                    slippage_bps=slip_bps,
                    quote_latency_ms=lat_ms,
                    routing_venue=ven,
                )
            )

        session.commit()

        # 6. Seed Fundamentals & Earnings Events
        logger.info("6. Seeding point-in-time fundamentals and earnings events...")
        session.execute(delete(FundamentalFiling))
        session.execute(delete(EarningsEvent))
        session.commit()

        fund_data = [
            ("NVDA", date(2024, 7, 31), datetime(2024, 8, 28, 20, 15, tzinfo=UTC), "Q2", {"roic": 0.542, "sloan_accrual": 0.012, "fcf_yield": 0.028, "ev_ebitda": 38.5, "pe_ratio": 42.1, "gross_margin": 0.75, "operating_margin": 0.62, "debt_to_equity": 0.18, "quality_score": 94, "value_score": 58, "piotroski_f_score": 9}),
            ("MSFT", date(2024, 6, 30), datetime(2024, 7, 30, 20, 5, tzinfo=UTC), "Q4", {"roic": 0.285, "sloan_accrual": 0.021, "fcf_yield": 0.031, "ev_ebitda": 24.2, "pe_ratio": 34.5, "gross_margin": 0.70, "operating_margin": 0.44, "debt_to_equity": 0.42, "quality_score": 88, "value_score": 62, "piotroski_f_score": 8}),
            ("AAPL", date(2024, 6, 29), datetime(2024, 8, 1, 20, 30, tzinfo=UTC), "Q3", {"roic": 0.482, "sloan_accrual": -0.015, "fcf_yield": 0.038, "ev_ebitda": 22.8, "pe_ratio": 31.2, "gross_margin": 0.46, "operating_margin": 0.31, "debt_to_equity": 1.45, "quality_score": 85, "value_score": 65, "piotroski_f_score": 8}),
            ("GOOGL", date(2024, 6, 30), datetime(2024, 7, 23, 20, 0, tzinfo=UTC), "Q2", {"roic": 0.298, "sloan_accrual": 0.018, "fcf_yield": 0.045, "ev_ebitda": 18.4, "pe_ratio": 23.6, "gross_margin": 0.57, "operating_margin": 0.32, "debt_to_equity": 0.10, "quality_score": 91, "value_score": 78, "piotroski_f_score": 9}),
            ("AMZN", date(2024, 6, 30), datetime(2024, 8, 1, 20, 10, tzinfo=UTC), "Q2", {"roic": 0.165, "sloan_accrual": 0.032, "fcf_yield": 0.035, "ev_ebitda": 17.5, "pe_ratio": 38.0, "gross_margin": 0.48, "operating_margin": 0.10, "debt_to_equity": 0.65, "quality_score": 82, "value_score": 70, "piotroski_f_score": 7}),
            ("META", date(2024, 6, 30), datetime(2024, 7, 31, 20, 5, tzinfo=UTC), "Q2", {"roic": 0.342, "sloan_accrual": 0.008, "fcf_yield": 0.042, "ev_ebitda": 19.8, "pe_ratio": 26.4, "gross_margin": 0.81, "operating_margin": 0.38, "debt_to_equity": 0.24, "quality_score": 92, "value_score": 74, "piotroski_f_score": 8}),
            ("TSLA", date(2024, 6, 30), datetime(2024, 7, 23, 20, 30, tzinfo=UTC), "Q2", {"roic": 0.125, "sloan_accrual": 0.045, "fcf_yield": 0.015, "ev_ebitda": 42.0, "pe_ratio": 55.0, "gross_margin": 0.18, "operating_margin": 0.07, "debt_to_equity": 0.12, "quality_score": 64, "value_score": 45, "piotroski_f_score": 6}),
        ]

        for sym, r_date, f_date, per, metrics in fund_data:
            session.add(
                FundamentalFiling(
                    symbol=sym,
                    report_date=r_date,
                    filing_date=f_date,
                    period=per,
                    metrics=json.dumps(metrics),
                )
            )

        earnings_data = [
            ("NVDA", date.today() + timedelta(days=12), "AMC", "Q3", Decimal("0.75"), None, Decimal("32500000000.00"), None),
            ("AAPL", date.today() + timedelta(days=28), "AMC", "Q4", Decimal("1.58"), None, Decimal("94500000000.00"), None),
            ("MSFT", date.today() + timedelta(days=22), "AMC", "Q1", Decimal("3.10"), None, Decimal("64500000000.00"), None),
            ("AMZN", date.today() + timedelta(days=25), "AMC", "Q3", Decimal("1.14"), None, Decimal("158000000000.00"), None),
            ("TSLA", date.today() + timedelta(days=8), "AMC", "Q3", Decimal("0.62"), None, Decimal("25500000000.00"), None),
        ]
        for sym, e_date, tod, fp, eps_est, eps_act, rev_est, rev_act in earnings_data:
            session.add(
                EarningsEvent(
                    symbol=sym,
                    event_date=e_date,
                    time_of_day=tod,
                    fiscal_period=fp,
                    eps_estimated=eps_est,
                    eps_actual=eps_act,
                    revenue_estimated=rev_est,
                    revenue_actual=rev_act,
                )
            )

        session.commit()

        # 7. Seed News Articles & LLM Narrative Scores
        logger.info("7. Seeding news articles and structured LLM narrative scores...")
        session.execute(delete(NewsScore))
        session.execute(delete(NewsArticle))
        session.commit()

        news_items = [
            (
                "art_001",
                "alpaca_news",
                "https://finance.yahoo.com/news/nvidia-blackwell-demand-surges-120000.html",
                "NVIDIA Blackwell Ultra Architecture Enters Mass Production with Full Cloud Hyperscaler Commitments",
                "NVIDIA CEO Jensen Huang confirmed unprecedented customer demand across all major cloud service providers for the next-generation Blackwell B200 accelerators.",
                "Full story text detailing Blackwell GPU ramp, sovereign AI initiatives, and multi-billion-dollar hyperscaler order books.",
                datetime.now(UTC) - timedelta(hours=4),
                ["NVDA", "MSFT", "GOOGL"],
                "hash_art_001",
                (Decimal("0.92"), Decimal("0.95"), "MEDIUM_TERM", Decimal("0.88"), "BULLISH", Decimal("0.96"), "Massive hyperscaler capex commitment directly reinforces multi-quarter hardware compute moat.", 240),
            ),
            (
                "art_002",
                "alpaca_news",
                "https://finance.yahoo.com/news/microsoft-copilot-enterprise-arr-140000.html",
                "Microsoft Announces 60% Surge in M365 Copilot Enterprise Seats and AI Cloud ARR Growth",
                "Microsoft Corporation revealed accelerating monetization of enterprise generative AI services, with Azure AI customers expanding deployments.",
                "Detailed revenue breakdown covering Office 365 Copilot adoption and intelligent cloud segment run rates.",
                datetime.now(UTC) - timedelta(hours=8),
                ["MSFT"],
                "hash_art_002",
                (Decimal("0.78"), Decimal("0.89"), "MEDIUM_TERM", Decimal("0.72"), "BULLISH", Decimal("0.92"), "Strong monetization metrics dispel concerns regarding generative AI capex payback periods.", 195),
            ),
            (
                "art_003",
                "alpaca_news",
                "https://finance.yahoo.com/news/apple-intelligence-rollout-160000.html",
                "Apple Intelligence Visual Intelligence Features Roll Out to Developer Betas Worldwide",
                "Apple expands device-side AI features across iPhone 16 Pro hardware lineup with on-device privacy-preserving foundation models.",
                "Overview of upcoming iOS release cycle, Siri foundation model integrations, and carrier upgrade subsidies.",
                datetime.now(UTC) - timedelta(hours=14),
                ["AAPL"],
                "hash_art_003",
                (Decimal("0.65"), Decimal("0.82"), "SHORT_TERM", Decimal("0.60"), "BULLISH", Decimal("0.88"), "Positive upgrade catalyst for consumer hardware replacement supercycle.", 180),
            ),
            (
                "art_004",
                "alpaca_news",
                "https://finance.yahoo.com/news/tesla-robotaxi-regulatory-filing-180000.html",
                "Tesla Submits California DMV Autonomous Commercial Fleet Operating Permit Application",
                "Tesla has formally filed preliminary documentation for commercial Cybercab fleet testing in select urban pilot zones.",
                "Discussion of state regulatory milestones, hardware 4 sensor suites, and unsupervised FSD validation timelines.",
                datetime.now(UTC) - timedelta(hours=20),
                ["TSLA"],
                "hash_art_004",
                (Decimal("0.58"), Decimal("0.85"), "LONG_TERM", Decimal("0.85"), "BULLISH", Decimal("0.78"), "High optionality on autonomous mobility network validation, subject to state regulatory timelines.", 215),
            ),
        ]

        for a_id, src, url, title, summ, content, pub_at, syms, c_hash, score_tuple in news_items:
            art = NewsArticle(
                id=a_id,
                source=src,
                url=url,
                title=title,
                summary=summ,
                content=content,
                published_at=pub_at,
                symbols=json.dumps(syms),
                content_hash=c_hash,
            )
            session.add(art)
            session.flush()

            sent, rel, hor, nov, imp, conf, rat, lat = score_tuple
            session.add(
                NewsScore(
                    article_id=a_id,
                    model_name="claude-3-5-sonnet-20241022",
                    prompt_version="1.0.0",
                    prompt_hash="prompt_news_sentiment_v1",
                    sentiment_score=sent,
                    relevance_score=rel,
                    horizon=hor,
                    novelty_score=nov,
                    impact=imp,
                    confidence=conf,
                    rationale=rat,
                    scored_at=pub_at + timedelta(seconds=15),
                    latency_ms=lat,
                )
            )

        session.commit()

        # 8. Seed ECB Reference Exchange Rates & Tax Lots / Events (Phase 9)
        logger.info("8. Seeding ECB EUR/USD exchange rates and tax accounting lots...")
        session.execute(delete(TaxEvent))
        session.execute(delete(TaxLot))
        session.execute(delete(ECBExchangeRate))
        session.commit()

        # ECB rates
        for d_idx in range(60):
            r_date = date.today() - timedelta(days=d_idx)
            if r_date.weekday() < 5:
                session.add(
                    ECBExchangeRate(
                        rate_date=r_date,
                        base_currency="EUR",
                        target_currency="USD",
                        rate=Decimal(str(round(1.0850 + 0.0005 * np.sin(d_idx), 4))),
                    )
                )

        session.commit()

        # Tax lots & events
        tax_lots_data = [
            ("lot_001", "NVDA", "AKTIEN", date(2024, 1, 15), datetime(2024, 1, 15, 15, 30, tzinfo=UTC), 100, 0, Decimal("54.50"), Decimal("1.0920"), Decimal("49.91"), Decimal("4991.00"), Decimal("1.50"), "CLOSED", datetime(2024, 6, 18, 16, 0, tzinfo=UTC)),
            ("lot_002", "MSFT", "AKTIEN", date(2024, 2, 10), datetime(2024, 2, 10, 15, 30, tzinfo=UTC), 50, 0, Decimal("405.00"), Decimal("1.0850"), Decimal("373.27"), Decimal("18663.50"), Decimal("2.00"), "CLOSED", datetime(2024, 7, 22, 16, 0, tzinfo=UTC)),
            ("lot_003", "NVDA", "AKTIEN", date(2024, 6, 20), datetime(2024, 6, 20, 15, 30, tzinfo=UTC), 150, 150, Decimal("124.50"), Decimal("1.0710"), Decimal("116.25"), Decimal("17437.50"), Decimal("2.50"), "OPEN", None),
            ("lot_004", "AAPL", "AKTIEN", date(2024, 7, 10), datetime(2024, 7, 10, 15, 30, tzinfo=UTC), 120, 120, Decimal("215.00"), Decimal("1.0820"), Decimal("198.71"), Decimal("23845.20"), Decimal("2.50"), "OPEN", None),
        ]

        for l_id, sym, cat, b_d, b_ts, q_i, q_r, b_px_u, fx_b, b_px_e, cost_e, comm_e, stat, cl_at in tax_lots_data:
            session.add(
                TaxLot(
                    id=l_id,
                    symbol=sym,
                    asset_category=cat,
                    buy_date=b_d,
                    buy_ts=b_ts,
                    quantity_initial=q_i,
                    quantity_remaining=q_r,
                    buy_price_usd=b_px_u,
                    buy_fx_rate_eur_usd=fx_b,
                    buy_price_eur=b_px_e,
                    total_cost_eur=cost_e,
                    commission_eur=comm_e,
                    status=stat,
                    closed_at=cl_at,
                )
            )

        tax_events_data = [
            ("evt_001", "lot_001", "NVDA", "AKTIEN", 2024, date(2024, 6, 18), datetime(2024, 6, 18, 16, 0, tzinfo=UTC), 100, Decimal("49.91"), Decimal("131.50"), Decimal("1.0740"), Decimal("122.44"), Decimal("12244.00"), Decimal("4991.00"), Decimal("2.00"), Decimal("7251.00"), True, Decimal("1812.75"), Decimal("99.70"), Decimal("0.00"), Decimal("1912.45")),
            ("evt_002", "lot_002", "MSFT", "AKTIEN", 2024, date(2024, 7, 22), datetime(2024, 7, 22, 16, 0, tzinfo=UTC), 50, Decimal("373.27"), Decimal("448.00"), Decimal("1.0890"), Decimal("411.39"), Decimal("20569.50"), Decimal("18663.50"), Decimal("2.50"), Decimal("1903.50"), True, Decimal("475.88"), Decimal("26.17"), Decimal("0.00"), Decimal("502.05")),
        ]

        for e_id, l_id, sym, cat, yr, s_d, s_ts, qty, b_px_e, s_px_u, fx_s, s_px_e, proc_e, cost_e, comm_e, gn_e, is_g, kest, soli, kirch, tot_tx in tax_events_data:
            session.add(
                TaxEvent(
                    id=e_id,
                    tax_lot_id=l_id,
                    symbol=sym,
                    asset_category=cat,
                    tax_year=yr,
                    sell_date=s_d,
                    sell_ts=s_ts,
                    quantity=qty,
                    buy_price_eur=b_px_e,
                    sell_price_usd=s_px_u,
                    sell_fx_rate_eur_usd=fx_s,
                    sell_price_eur=s_px_e,
                    proceeds_eur=proc_e,
                    cost_basis_eur=cost_e,
                    commission_eur=comm_e,
                    gain_loss_eur=gn_e,
                    is_gain=is_g,
                    kest_amount_eur=kest,
                    soli_amount_eur=soli,
                    kirchensteuer_eur=kirch,
                    total_tax_eur=tot_tx,
                )
            )

        session.commit()
        logger.info("Database seeding successfully completed!")


if __name__ == "__main__":
    seed_all()
