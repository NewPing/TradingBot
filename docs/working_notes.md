# ATLAS — Working Notes

## CURRENT STATE
- **Phase**: 3 (Versioning & Dashboard v1) — Completed & Verified
- **Active Branch**: `phase-3/versioning-dashboard`
- **Current State**: Phase 3 complete. Implemented `StrategyVersionRegistry` with immutable spec hashing, lineage graphs, and `SpecImmutabilityError` protection. Implemented `RunRegistry` capturing full reproducibility metadata (`git_sha`, `spec_hash`, `cost_model_hash`, `seed`, `lib_versions`, `data_snapshot_id`). Built `TrialTracker` for sacred multiple-testing budget accounting. Implemented FastAPI routers for `/versions`, `/runs`, `/compare`, `/trials`, and `/signals/explore`. Scaffolded and built Next.js 15 (App Router) Dashboard with Overview, Versions & Lineage, Compare View, Run Detail with Reproducibility Footer, and Signals Explorer with terminal dark theme. All 117 tests passing, strict Mypy clean, Ruff clean, Next.js production build verified.

## NEXT UP
1. Human sign-off on Phase 3 gate.
2. Proceed to Phase 4 (Portfolio, Risk & Paper Trading): Bucket ledger with isolated sub-accounts, position sizing, hard limits, kill switches, `AlpacaPaperBroker`, live runner daemon (APScheduler), crash recovery, WebSocket streaming, and alerting.

## OPEN QUESTIONS
- None for Phase 3.

## SESSION LOG
### 2026-08-23 — Session 3: Phase 2 Engine & Baselines
- Implemented `HistoricalMarketContext` in `atlas/core/context.py` strictly restricting queries to timestamps $\le \text{clock.now}$ with `LookaheadError`.
- Implemented pessimistic transaction cost model `DefaultCostModelV1` (`costs.default_v1`) in `atlas/backtest/costs.py` with market-impact square-root slippage ($k=1.0$), spread estimation, SEC & FINRA TAF sell regulatory fees, and broker commissions.
- Built `SimBroker` in `atlas/backtest/broker.py` enforcing $t+1$ execution discipline, non-fractional whole-share position accounting, and gap-aware stop losses.
- Built L1 technical indicator routines in `atlas/signals/indicators.py` (SMA, EMA, RSI, MACD, ATR, Bollinger, Momentum/ROC, Realized Vol, Volume Z-Score, 52w range) and providers in `atlas/signals/l1_technical.py`.
- Implemented `WeightedConfidenceAggregator` in `atlas/signals/aggregator.py` with confidence weighting and abstention gating.
- Built `SizingCalculator` (volatility budgeting & conviction scaling) and position policies in `atlas/portfolio/policies.py`.
- Implemented `StrategySpec` loader with SHA-256 spec hashing and component builders in `atlas/strategies/`.
- Authored baseline YAML strategy specifications: `core_trend_v1.yaml`, `swing_meanrev_v1.yaml`, `buy_hold_spy.yaml`, `sixty_forty.yaml`, `equal_weight_universe.yaml`.
- Implemented `BacktestEngine` with single-threaded §8.1 event loop, comprehensive `PerformanceMetrics` module in `atlas/backtest/metrics.py`, and CLI in `atlas/backtest/cli.py`.
- Added 30+ new unit, property (`hypothesis`), and lookahead verification tests (106 total tests, 83.2% total coverage, $\ge 85\%$ in core backtest/portfolio/signals).
- Verification clean with `mypy --strict` on 52 files, `ruff check`, and `ruff format`.

### 2026-08-23 — Session 4: Developer/Terminal Dark Re-Theme
- Centralized trading-semantic dark developer/terminal color palette:
  - Surfaces: `--bg` (`#0a0a0a`), `--bg-sidebar` (`#0d0d0d`), `--surface` (`#141414`), `--surface-2` (`#1c1c1c`), `--active` (`#1a1a1a`).
  - Borders: `--border` (`#262626`), `--border-subtle` (`#1f1f1f`).
  - Typography: `--text-1` (`#ededed`), `--text-2` (`#a1a1aa`), `--text-3` (`#71717a`).
  - Semantics: `--pos` (`#22c55e` primary accent / gains), `--neg` (`#ef4444` errors / losses), `--warn` (`#f59e0b`), `--info` (`#38bdf8`).
- Updated FastAPI splash page in `atlas/api/main.py` with custom CSS variables, status dot, monospace typography, and hairline borders.
- Documented Theme & Color System in `docs/ARCHITECTURE.md`, `docs/MASTER_PLAN.md`, and `README.md`.
- Verified 100% clean check suite: 106 tests passing, strict mypy clean, ruff lint and format clean.

### 2026-08-23 — Session 5: Phase 3 Versioning & Dashboard v1
- Created Alembic migration `0002_phase3_versioning_runs_trials` and SQLAlchemy models for `strategy_versions`, `runs`, `run_metrics`, `equity_curve`, `run_trades`, and `trials`.
- Implemented `StrategyVersionRegistry` with immutable spec hashing, lineage graphs, and `SpecImmutabilityError` protection when a spec with existing runs is modified.
- Implemented `RunRegistry` capturing full environment reproducibility metadata (`git_sha`, `spec_hash`, `cost_model_hash`, `seed`, `lib_versions`, `data_snapshot_id`).
- Implemented `TrialTracker` for sacred multiple-testing trial counters and weekly testing budget consumption.
- Implemented FastAPI routers for `/api/v1/versions`, `/api/v1/runs`, `/api/v1/compare`, `/api/v1/trials`, and `/api/v1/signals/explore`.
- Scaffolded and implemented Next.js 15 (App Router) dashboard with dark developer/terminal theme: Overview (`/`), Versions & Lineage (`/versions`), Run Comparison Matrix (`/compare`), Run Detail with Reproducibility Footer (`/runs/[id]`), and Signals Explorer (`/signals`).
- Added unit and integration tests covering spec immutability, run registry, multi-run comparisons, and API endpoints (117 total tests passing).
- Verified full verification suite: `ruff check`, `ruff format --check`, `mypy --strict` on 65 files, and Next.js production build (`npm run build`).
