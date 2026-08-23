# ATLAS — Working Notes

## CURRENT STATE
- **Phase**: 2 (Engine & Baselines) — Completed & Verified
- **Active Branch**: `phase-2/engine-baselines`
- **Current State**: Phase 2 backtesting engine and baselines complete. HistoricalMarketContext (zero-lookahead gate), SimBroker with strictly enforced $t+1$ fill timing, pessimistic cost model `costs.default_v1` (spread, market-impact slippage, SEC + FINRA regulatory fees, commissions, gap stops), L1 technical indicator library & `WeightedConfidenceAggregator`, 3 position policies (`TopNLongOnlyPolicy`, `ThresholdLongOnlyPolicy`, `TargetWeightPolicy`), volatility-targeted sizing calculator, YAML strategy spec loader with deterministic SHA-256 spec hashing, baseline strategy specifications (`core_trend_v1`, `swing_meanrev_v1`, `buy_hold_spy`, `sixty_forty`, `equal_weight_universe`), deterministic event loop backtest engine, metrics calculator, and CLI runner.

## NEXT UP
1. Human sign-off on Phase 2.
2. Proceed to Phase 3 (Versioning & Dashboard v1): Strategy version registry with immutability enforcement & lineage, Run registry with reproducibility metadata, trial counter, API endpoints (`/versions`, `/runs`, `/compare`), Next.js dashboard views.

## OPEN QUESTIONS
- None for Phase 2.

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
