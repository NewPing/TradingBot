"""CLI commands for ATLAS data management: ingest, snapshot, validate, coverage."""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from collections.abc import Sequence
from datetime import date

from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

from atlas.core.config import get_settings
from atlas.core.types import Bar, Symbol
from atlas.data.ingest import DataIngestPipeline
from atlas.data.models import Bar1D, NewsArticle
from atlas.data.providers.alpaca import AlpacaMarketDataProvider
from atlas.data.providers.alpaca_news import AlpacaNewsProvider
from atlas.data.providers.base import BaseDataProvider
from atlas.data.providers.tiingo import TiingoProvider
from atlas.data.providers.yfinance import YFinanceProvider
from atlas.data.snapshots import SnapshotManager

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("atlas.data.cli")


def get_db_session() -> Session:
    settings = get_settings()
    engine = create_engine(settings.atlas_db_url)
    return Session(engine)


async def handle_ingest(args: argparse.Namespace) -> None:
    symbols = [Symbol(s.strip().upper()) for s in args.symbols.split(",")]
    start_d = date.fromisoformat(args.start)
    end_d = date.fromisoformat(args.end)

    provider: BaseDataProvider
    if args.provider == "alpaca":
        provider = AlpacaMarketDataProvider()
    elif args.provider == "yfinance":
        provider = YFinanceProvider()
    else:
        provider = TiingoProvider()

    pipeline = DataIngestPipeline(primary_provider=provider)
    session = None if args.dry_run else get_db_session()

    for sym in symbols:
        logger.info("Starting ingest for %s...", sym)
        bars, issues, result = await pipeline.ingest_symbol(
            symbol=sym,
            start_date=start_d,
            end_date=end_d,
            session=session,
        )
        logger.info(
            "Completed %s: %d bars ingested, %d corporate actions, %d issues flagged",
            sym,
            result.bars_ingested,
            result.corporate_actions_count,
            result.issues_found,
        )


def handle_snapshot(args: argparse.Namespace) -> None:
    snap_date = date.fromisoformat(args.date) if args.date else date.today()
    session = get_db_session()
    manager = SnapshotManager()

    # Query all bars up to snap_date
    stmt = select(Bar1D).where(func.date(Bar1D.ts) <= snap_date).order_by(Bar1D.symbol, Bar1D.ts)
    db_bars = session.scalars(stmt).all()

    bars = [
        Bar(
            symbol=Symbol(b.symbol),
            ts=b.ts,
            open=b.open,
            high=b.high,
            low=b.low,
            close=b.close,
            volume=b.volume,
            adj_factor=b.adj_factor,
            vwap=b.vwap,
            source=b.source,
        )
        for b in db_bars
    ]

    meta = manager.create_snapshot(snapshot_date=snap_date, bars=bars)
    logger.info(
        "Created snapshot %s: %d symbols, %d bars, hash: %s",
        meta.snapshot_id,
        meta.symbols_count,
        meta.bars_count,
        meta.sha256_hash,
    )


async def handle_ingest_news(args: argparse.Namespace) -> None:
    import json
    from datetime import UTC, datetime, timedelta

    symbols = [Symbol(s.strip().upper()) for s in args.symbols.split(",")] if args.symbols else None
    days = int(args.days)
    end_dt = datetime.now(UTC)
    start_dt = end_dt - timedelta(days=days)

    provider = AlpacaNewsProvider()
    logger.info("Fetching news from Alpaca for symbols: %s (last %d days)", symbols, days)
    raw_articles = await provider.fetch_news(
        symbols=symbols,
        start=start_dt,
        end=end_dt,
        limit=int(args.limit),
        include_content=True,
    )

    logger.info("Received %d raw articles from Alpaca", len(raw_articles))
    session = None if args.dry_run else get_db_session()

    ingested_count = 0
    duplicate_count = 0

    for raw in raw_articles:
        norm = provider.normalize_article(raw)
        if session:
            # Check for existing article by content_hash or id
            existing = session.scalar(
                select(NewsArticle).where(
                    (NewsArticle.content_hash == norm["content_hash"])
                    | (NewsArticle.id == norm["id"])
                )
            )
            if existing:
                duplicate_count += 1
                continue

            article = NewsArticle(
                id=norm["id"],
                source=norm["source"],
                url=norm["url"],
                title=norm["title"],
                summary=norm["summary"],
                content=norm["content"],
                published_at=norm["published_at"],
                symbols=json.dumps([str(s) for s in norm["symbols"]]),
                content_hash=norm["content_hash"],
            )
            session.add(article)
            ingested_count += 1

    if session:
        session.commit()
        session.close()

    logger.info(
        "News ingestion complete: %d inserted, %d duplicates skipped",
        ingested_count,
        duplicate_count,
    )


async def handle_ingest_benchmark(args: argparse.Namespace) -> None:
    benchmark_symbols = [Symbol(s.strip().upper()) for s in args.benchmarks.split(",")]
    start_d = date.fromisoformat(args.start)
    end_d = date.fromisoformat(args.end)

    provider: BaseDataProvider
    if args.provider == "alpaca":
        provider = AlpacaMarketDataProvider()
    elif args.provider == "tiingo":
        provider = TiingoProvider()
    else:
        provider = YFinanceProvider()

    pipeline = DataIngestPipeline(primary_provider=provider)
    session = None if args.dry_run else get_db_session()

    for sym in benchmark_symbols:
        logger.info("Ingesting 100%% real historical benchmark data for %s from %s to %s...", sym, start_d, end_d)
        bars, issues, result = await pipeline.ingest_symbol(
            symbol=sym,
            start_date=start_d,
            end_date=end_d,
            session=session,
        )
        logger.info(
            "Benchmark %s ingested: %d bars, %d issues flagged",
            sym,
            result.bars_ingested,
            result.issues_found,
        )


def handle_coverage(args: argparse.Namespace) -> None:
    _ = args
    session = get_db_session()
    stmt = select(
        Bar1D.symbol,
        func.count(Bar1D.ts).label("bar_count"),
        func.min(Bar1D.ts).label("min_ts"),
        func.max(Bar1D.ts).label("max_ts"),
    ).group_by(Bar1D.symbol)

    results = session.execute(stmt).all()
    print(f"\n{'SYMBOL':<10} | {'BARS':<8} | {'START':<20} | {'END':<20}")
    print("-" * 65)
    for row in results:
        sym, count, min_t, max_t = row
        print(f"{sym:<10} | {count:<8} | {str(min_t):<20} | {str(max_t):<20}")
    print(f"\nTotal tracked symbols: {len(results)}\n")


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="ATLAS Data Management CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # Ingest
    ingest_p = subparsers.add_parser("ingest", help="Ingest daily price data from provider")
    ingest_p.add_argument(
        "--symbols", required=True, help="Comma-separated symbols, e.g. SPY,AAPL,MSFT"
    )
    ingest_p.add_argument("--start", default="2005-01-01", help="Start date (YYYY-MM-DD)")
    ingest_p.add_argument("--end", default=date.today().isoformat(), help="End date (YYYY-MM-DD)")
    ingest_p.add_argument("--provider", default="tiingo", choices=["tiingo", "alpaca", "yfinance"])
    ingest_p.add_argument("--dry-run", action="store_true", help="Do not write to DB")

    # Snapshot
    snap_p = subparsers.add_parser("snapshot", help="Create deterministic Parquet snapshot")
    snap_p.add_argument(
        "--date", default=date.today().isoformat(), help="Snapshot date (YYYY-MM-DD)"
    )

    # Ingest News
    news_p = subparsers.add_parser("ingest-news", help="Ingest financial news articles")
    news_p.add_argument(
        "--symbols", default="", help="Comma-separated symbols, e.g. AAPL,MSFT,NVDA"
    )
    news_p.add_argument("--days", type=int, default=30, help="Lookback window in days")
    news_p.add_argument("--limit", type=int, default=50, help="Max articles per request")
    news_p.add_argument("--dry-run", action="store_true", help="Do not persist to database")

    # Ingest Benchmark (SPY / QQQ)
    bm_p = subparsers.add_parser("ingest-benchmark", help="Ingest real historical benchmark series (SPY, QQQ)")
    bm_p.add_argument(
        "--benchmarks", default="SPY,QQQ", help="Comma-separated benchmark symbols"
    )
    bm_p.add_argument("--start", default="2005-01-01", help="Start date (YYYY-MM-DD)")
    bm_p.add_argument("--end", default=date.today().isoformat(), help="End date (YYYY-MM-DD)")
    bm_p.add_argument("--provider", default="yfinance", choices=["yfinance", "tiingo", "alpaca"])
    bm_p.add_argument("--dry-run", action="store_true", help="Do not write to DB")

    # Coverage
    subparsers.add_parser("coverage", help="Display symbol bar coverage matrix")

    args = parser.parse_args(argv)

    if args.command == "ingest":
        asyncio.run(handle_ingest(args))
    elif args.command == "ingest-benchmark":
        asyncio.run(handle_ingest_benchmark(args))
    elif args.command == "ingest-news":
        asyncio.run(handle_ingest_news(args))
    elif args.command == "snapshot":
        handle_snapshot(args)
    elif args.command == "coverage":
        handle_coverage(args)

    return 0


if __name__ == "__main__":
    sys.exit(main())
