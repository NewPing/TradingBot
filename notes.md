# ATLAS — Engineering Notes & Session Log

## CURRENT STATE
- **Phase**: 2 (Engine & Baselines) — Completed & Verified
- **Active Branch**: `phase-2/engine-baselines`
- **Current Milestone**: Single-threaded backtesting event loop, HistoricalMarketContext zero-lookahead gating, SimBroker with $t+1$ fill timing, pessimistic cost model `costs.default_v1`, L1 technical signal provider library, WeightedConfidenceAggregator, position policies (Top-N, Threshold hysteresis, Target Weight), volatility-targeted position sizing, YAML strategy spec loader with canonical SHA-256 hashing, baseline strategies, metrics module, CLI runner, and lookahead/deterministic replay test suite.
- **Working Components**:
  - `atlas.core.context`: `HistoricalMarketContext` preventing any future timestamp lookahead.
  - `atlas.backtest.costs`: `DefaultCostModelV1` implementing spread, square-root slippage ($k=1.0$), SEC & FINRA regulatory fees, commissions, and cash yield.
  - `atlas.backtest.broker`: `SimBroker` implementing $t+1$ order execution, stop triggers, whole-share integer quantities, and strict `Money` accounting.
  - `atlas.signals`: Indicators (SMA, EMA, RSI, MACD, ATR, Bollinger, Momentum, Volatility, 52w pos, Volume Z) and `WeightedConfidenceAggregator`.
  - `atlas.portfolio`: Sizing calculator and policies (`TopNLongOnlyPolicy`, `ThresholdLongOnlyPolicy`, `TargetWeightPolicy`).
  - `atlas.strategies`: `StrategySpec` model, loader, validator, SHA-256 hashing, and factory builders.
  - `strategies/*.yaml`: Baseline specifications (`core_trend_v1`, `swing_meanrev_v1`, `buy_hold_spy`, `sixty_forty`, `equal_weight_universe`).
  - `atlas.backtest.engine` & `atlas.backtest.metrics`: Backtest event loop, performance & risk metrics calculation, and CLI.
  - `tests`: 106 unit, hypothesis, and deterministic replay tests passing, 83.2% total coverage, 100% clean strict mypy & ruff.
- **Blocked / Incomplete**: Awaiting human approval for Phase 2 gate before proceeding to Phase 3 (Versioning & Dashboard v1).

## NEXT UP
1. [x] Phase 2 implementation & verification.
2. [ ] Human sign-off on Phase 2 gate.
3. [ ] Proceed to Phase 3 (Versioning & Dashboard v1).

## OPEN QUESTIONS & DECISIONS
- All Phase 2 specifications implemented per authoritative documentation.

## SESSION LOG
### 2026-08-23 — Session 3: Phase 2 Engine & Baselines Complete
- Implemented `HistoricalMarketContext` with zero-lookahead enforcement.
- Built pessimistic transaction cost model `costs.default_v1`.
- Built `SimBroker` with $t+1$ execution discipline and stop loss support.
- Built L1 technical indicator library, signal providers, and `WeightedConfidenceAggregator`.
- Built position policies and volatility sizing calculator.
- Created StrategySpec loader, spec hash calculation, and baseline strategy YAML files.
- Built `BacktestEngine`, `PerformanceMetrics`, and CLI subcommands.
- Verified all 106 tests, `mypy --strict`, `ruff check`, and `ruff format`.

### 2026-08-23 — Session 4: Developer/Terminal Dark Re-Theme
- Implemented semantic dark developer/terminal design token system:
  - Surfaces: `--bg` (`#0a0a0a`), `--bg-sidebar` (`#0d0d0d`), `--surface` (`#141414`), `--surface-2` (`#1c1c1c`), `--active` (`#1a1a1a`).
  - Borders: `--border` (`#262626`), `--border-subtle` (`#1f1f1f`).
  - Text: `--text-1` (`#ededed`), `--text-2` (`#a1a1aa`), `--text-3` (`#71717a`).
  - Trading Semantics: `--pos` (`#22c55e` primary accent / gains), `--neg` (`#ef4444` errors / losses), `--warn` (`#f59e0b`), `--info` (`#38bdf8`).
- Updated FastAPI root HTML/CSS in `atlas/api/main.py` with custom CSS variables and terminal styling.
- Documented Theme & Color System in `docs/ARCHITECTURE.md`, `docs/MASTER_PLAN.md`, and `README.md`.
- Full verification passed (`ruff`, `mypy --strict`, `pytest`).
