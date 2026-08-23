"""Unit tests for backtest CLI commands."""

from __future__ import annotations

from datetime import date

from click.testing import CliRunner

from atlas.backtest.cli import backtest_cli
from atlas.core.types import Symbol
from tests.unit.test_backtest_lookahead import generate_synthetic_dataset


def test_backtest_cli_run_with_snapshot(tmp_path) -> None:  # type: ignore[no-untyped-def]
    runner = CliRunner()
    symbols = [Symbol("SPY"), Symbol("AAPL")]
    df = generate_synthetic_dataset(symbols, date(2021, 1, 1), date(2021, 6, 30))

    snap_dir = tmp_path / "snapshot_test_snap"
    snap_dir.mkdir(parents=True, exist_ok=True)
    df.write_parquet(snap_dir / "bars_1d.parquet")

    result = runner.invoke(
        backtest_cli,
        [
            "run",
            "--spec",
            "strategies/buy_hold_spy.yaml",
            "--start",
            "2021-01-01",
            "--end",
            "2021-06-30",
            "--snapshot",
            str(snap_dir),
            "--benchmark",
            "SPY",
        ],
    )

    assert result.exit_code == 0
    assert "BACKTEST RESULTS: buy_hold_spy" in result.output
    assert "CAGR:" in result.output
