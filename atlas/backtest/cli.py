"""CLI command interface for running ATLAS backtests."""

from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

import click
import polars as pl

from atlas.backtest.engine import BacktestEngine
from atlas.core.types import Symbol
from atlas.data.snapshots import SnapshotManager
from atlas.strategies.spec import StrategySpec


@click.group(name="backtest")
def backtest_cli() -> None:
    """ATLAS backtesting and evaluation engine commands."""
    pass


@backtest_cli.command(name="run")
@click.option(
    "--spec",
    "-s",
    required=True,
    type=click.Path(exists=True),
    help="Path to strategy YAML spec file.",
)
@click.option(
    "--start",
    required=False,
    type=str,
    default="2019-01-01",
    help="Backtest start date (YYYY-MM-DD).",
)
@click.option(
    "--end", required=False, type=str, default="2022-12-31", help="Backtest end date (YYYY-MM-DD)."
)
@click.option(
    "--snapshot",
    required=False,
    type=click.Path(exists=True),
    help="Path to Parquet snapshot directory.",
)
@click.option(
    "--benchmark", required=False, type=str, default="SPY", help="Benchmark symbol (e.g. SPY)."
)
def run_backtest_cmd(
    spec: str,
    start: str,
    end: str,
    snapshot: str | None,
    benchmark: str,
) -> None:
    """Run a deterministic backtest of a strategy specification."""
    try:
        start_d = date.fromisoformat(start)
        end_d = date.fromisoformat(end)
    except ValueError as e:
        click.echo(f"Error parsing date: {e}", err=True)
        sys.exit(1)

    click.echo(f"Loading strategy spec: {spec}")
    try:
        strategy_spec = StrategySpec.from_yaml(spec)
    except Exception as e:
        click.echo(f"Failed to parse strategy spec: {e}", err=True)
        sys.exit(1)

    click.echo(f"Strategy: {strategy_spec.name} (v{strategy_spec.version})")
    click.echo(f"Spec Hash: {strategy_spec.spec_hash()[:12]}...")

    # Load data
    if snapshot:
        snap_path = Path(snapshot)
        if snap_path.is_file() and snap_path.suffix == ".parquet":
            click.echo(f"Loading parquet directly from: {snap_path}")
            data_df = pl.read_parquet(snap_path)
        elif (snap_path / "bars_1d.parquet").exists():
            click.echo(f"Loading parquet from snapshot dir: {snap_path}")
            data_df = pl.read_parquet(snap_path / "bars_1d.parquet")
        else:
            click.echo(f"Loading snapshot data from: {snapshot}")
            snap_mgr = SnapshotManager(base_dir=snap_path.parent)
            data_df = snap_mgr.load_snapshot_dataframe(snap_path.name)
    else:
        # Check standard default snapshots directory
        default_snap_dir = Path("data/snapshots")
        if default_snap_dir.exists():
            snapshots = list(default_snap_dir.glob("snapshot_*"))
            if snapshots:
                latest_snap = sorted(snapshots)[-1]
                click.echo(f"Loading latest snapshot: {latest_snap.name}")
                data_df = pl.read_parquet(latest_snap / "bars_1d.parquet")
            else:
                click.echo("No snapshot found. Please provide --snapshot path.", err=True)
                sys.exit(1)
        else:
            click.echo("Snapshot directory not found. Please provide --snapshot.", err=True)
            sys.exit(1)

    bm_symbol = Symbol(benchmark) if benchmark else None

    click.echo(f"Running backtest from {start_d} to {end_d}...")
    engine = BacktestEngine(spec=strategy_spec, data=data_df)
    result = engine.run(start_date=start_d, end_date=end_d, benchmark_symbol=bm_symbol)

    m = result.metrics
    click.echo("=" * 60)
    click.echo(f"BACKTEST RESULTS: {strategy_spec.name}")
    click.echo("=" * 60)
    click.echo(f"Initial Capital:  {result.initial_capital}")
    click.echo(f"Final Equity:     {result.final_equity}")
    click.echo(f"Total Return:     {m.total_return:+.2%}")
    click.echo(f"CAGR:             {m.cagr:+.2%}")
    click.echo(f"Annualized Vol:   {m.annualized_vol:.2%}")
    click.echo(f"Downside Vol:     {m.downside_vol:.2%}")
    click.echo(f"Max Drawdown:     {m.max_drawdown:.2%} ({m.max_drawdown_days} days)")
    click.echo(f"Sharpe Ratio:     {m.sharpe_ratio:.2f}")
    click.echo(f"Sortino Ratio:    {m.sortino_ratio:.2f}")
    click.echo(f"Calmar Ratio:     {m.calmar_ratio:.2f}")
    click.echo(f"Total Fills:      {len(result.fills)}")
    click.echo(f"Exposure %:       {m.exposure_pct:.1%}")
    click.echo(f"Turnover:         {m.turnover:.2f}x")
    if m.benchmark_cagr is not None:
        click.echo("-" * 60)
        click.echo(f"Benchmark CAGR ({benchmark}): {m.benchmark_cagr:+.2%}")
        click.echo(f"Alpha:                        {m.alpha:+.2%}" if m.alpha else "Alpha: N/A")
        click.echo(f"Beta:                         {m.beta:.2f}" if m.beta else "Beta: N/A")
        click.echo(
            f"Correlation:                  {m.correlation:.2f}" if m.correlation else "Corr: N/A"
        )
    click.echo("=" * 60)
