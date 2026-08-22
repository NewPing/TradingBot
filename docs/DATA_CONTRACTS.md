# ATLAS — Data Contracts & Storage

## 4.1 Core Domain Types (`atlas/core/types.py`)

All frozen. `Money` wraps `Decimal` and strictly raises `TypeError` on `float` arithmetic.

```python
Symbol      = NewType("Symbol", str)          # uppercase, exchange-normalized
Money       # Decimal + currency, quantized to 4dp internally, 2dp for display
Bar         # symbol, ts (bar CLOSE, UTC), open, high, low, close, volume,
            # adj_factor, vwap|None, source, resolution
Signal      # provider, layer, symbol, ts, score[-1..1], confidence[0..1],
            # rationale: str, features: dict[str, float]
Order       # id, run_id, strategy_version_id, bucket, symbol, side, qty,
            # type(MARKET|LIMIT|STOP|STOP_LIMIT), tif, limit_px, stop_px,
            # created_ts, status, tags
Fill        # order_id, ts, qty, price, commission, fees, slippage_est, venue
Position    # symbol, bucket, qty, avg_price, opened_ts, unrealized, realized, stop_px
BucketId    # CORE | SWING | MOONSHOT | CASH   (enum)
SignalLayer # L1_TECHNICAL | L2_STATISTICAL | L3_FUNDAMENTAL | L4_NARRATIVE
RunMode     # BACKTEST | PAPER | SHADOW | LIVE
RunStatus   # QUEUED | RUNNING | COMPLETED | FAILED | ABORTED
```

## 4.2 Interfaces (Protocols)

```python
class MarketContext(Protocol):
    now: datetime                                  # tz-aware UTC, set by Clock
    def bars(self, symbol: Symbol, lookback: int, resolution: str = "1d") -> pl.DataFrame: ...
    def latest(self, symbol: Symbol, resolution: str = "1d") -> Bar | None: ...
    def universe(self) -> list[Symbol]: ...
    def fundamentals(self, symbol: Symbol) -> FundamentalSnapshot | None: ...   # point-in-time
    def news(self, symbol: Symbol, lookback_hours: int) -> list[NewsItem]: ...  # point-in-time
    def calendar_is_open(self) -> bool: ...
    # Every method filters ts <= now. No exceptions. No escape hatch.

class SignalProvider(Protocol):
    name: str
    version: str
    layer: SignalLayer
    def warmup_bars(self) -> int: ...
    def evaluate(self, ctx: MarketContext, symbol: Symbol) -> Signal | None: ...

class Broker(Protocol):
    def submit(self, order: Order) -> BrokerOrderRef: ...
    def cancel(self, ref: BrokerOrderRef) -> None: ...
    def positions(self) -> list[Position]: ...
    def account(self) -> AccountState: ...
    def on_fill(self, cb: Callable[[Fill], None]) -> None: ...
    def is_healthy(self) -> bool: ...
```

## 4.3 Database Schema (TimescaleDB)

**Hypertables:** `bars_1d`, `bars_1h`, `bars_1m`, `equity_curve`, `metrics_timeseries`, `news_items`

| Table | Key columns |
|---|---|
| `instruments` | symbol PK, name, exchange, sector, industry, listed_on, delisted_on, is_etf, adv_usd |
| `universe_snapshots` | snapshot_date, symbol — point-in-time index membership, prevents survivorship bias |
| `bars_1d` / `bars_1h` / `bars_1m` | (symbol, ts) PK, ohlcv, adj_factor, source, ingested_at |
| `corporate_actions` | symbol, ex_date, type(SPLIT\|DIVIDEND\|MERGER), ratio, amount |
| `fundamentals_pit` | symbol, report_date, filing_date (= when public), period, metrics JSONB |
| `news_items` | id, ts, source, symbols[], title, body_hash, url, author, raw JSONB |
| `news_scores` | news_id, model, model_version, sentiment, relevance, horizon, rationale |
| `strategy_versions` | id PK, family, version, spec_yaml, spec_hash, git_sha, parent_id, created_at, status, notes — immutable once a Run exists |
| `runs` | id PK, strategy_version_id, mode, start_ts, end_ts, universe_hash, data_snapshot_id, seed, lib_versions JSONB, status, cost_model_hash |
| `run_metrics` | run_id, metric_name, value, window — flat KV, easy to compare N versions |
| `orders` / `fills` | full lifecycle, FK to run_id |
| `positions_snapshots` | run_id, ts, symbol, bucket, qty, mv, unrealized |
| `equity_curve` | run_id, ts, total_equity, cash, per-bucket equity JSONB, drawdown |
| `trials` | id, hypothesis_id, params JSONB, run_id, outcome, counted for multiple-testing correction |
| `research_reports` | id, trial_ids[], verdict, markdown, created_at, human_decision |
| `data_health` | check_name, ts, symbol, severity, detail |
| `kill_switch_events` | ts, trigger, detail, auto_resolved, resolved_by, resolved_at |

## 4.4 Data Snapshots
Ingestion writes immutable, dated Parquet snapshots to `data/snapshots/<YYYY-MM-DD>/`. Backtests reference a `data_snapshot_id`.

## 4.5 Data Validation Checks
- Missing bar on a trading day: `data_health` warning; forward-fill forbidden.
- Zero volume on open day: flag, exclude symbol from universe that day.
- Move > 25% without corporate action: flag as suspect, cross-source confirmation.
- High < Low or Close outside [Low, High]: reject bar, alert.
- Cross-source close diff > 0.5% (Tiingo vs Alpaca): flag, prefer Tiingo, log.
- Adjusted series discontinuity vs corporate actions: block snapshot creation.
- Stale data: trigger kill switch `STALE_DATA` in live mode.

## Cost Model (`costs.default_v1`)
- Commission: Alpaca $0; IBKR $0.0035/share (min $0.35, max 1% of trade value).
- Regulatory fees: SEC $0.0000278 * sell notional + FINRA TAF $0.000166/share.
- Spread cost: Half-spread, estimated as `max(0.01, 0.0004 * price)` for ADV > $50M, `0.0010 * price` below.
- Slippage: `k * σ_daily * sqrt(order_notional / ADV)` with `k = 1.0`.
- Fills: Filled on next bar (`t+1`), never at same-bar close.
- Overnight gaps: Stops fill at next open, not stop price.
- Borrow cost: 3% annualized on short notional (Phase 7+).
- Idle cash yield: 4.0% annualized.
