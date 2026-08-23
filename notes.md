# ATLAS — Engineering Notes & Session Log

## CURRENT STATE
- **Phase**: 8 (The Research Loop) — Completed & Verified
- **Active Branch**: `phase-8/the-research-loop`
- **Current Milestone**: Autonomous Strategy Discovery & Research Loop (`HypothesisGenerator`, `SweepEngine`, `StatisticalGatekeeper` enforcing 8 validation gates §8.3, `HoldoutGuard` protecting 2023-present-90d partition, `ResearchReporter` generating markdown reports, `ResearchDaemon` headless runner, `TrialTracker` sacred multiple-testing budget accounting, FastAPI endpoints `/api/v1/research/*`, and Next.js Research & Discovery dashboard view `/research`).
- **Working Components**:
  - `atlas.data.models`: `ResearchHypothesis`, `ResearchSweep`, `ResearchReport`, and `HoldoutAccessLog` SQLAlchemy models with Alembic migration `0006_phase8_research_loop`.
  - `atlas.research.stats`: Deflated Sharpe Ratio (DSR), CSCV Probability of Backtest Overfitting (PBO), Monte Carlo trade permutations (1,000 iterations), and rolling walk-forward fold generators.
  - `atlas.research.gatekeeper`: `StatisticalGatekeeper` evaluating Walk-Forward, Parameter Perturbation, Monte Carlo, Cost Stress, Regime Breakdown, Sample Size, PBO/DSR, and Correlation Guard (<0.60).
  - `atlas.research.holdout`: Cryptographic holdout partition guard and authorization tracker.
  - `atlas.research.hypothesis`: 5 discovery modalities (Parameter refinement, Feature combo L1-L4, Regime conditioning, Genetic recombination).
  - `atlas.research.sweep`: Parameter grid and exploration runner with sacred `trials` ledger logging.
  - `atlas.research.daemon`: Headless background daemon orchestrating discovery iterations, validation, and reporting.
  - `atlas.api.routers.research`: REST endpoints for daemon telemetry, on-demand hypothesis formulation, sweeps, report browser, and candidate review queue.
  - `web/src/app/research`: Next.js Research & Discovery dashboard view with trial budget gauge, reports viewer, and 1-click Human Promotion Queue.
  - `tests`: 212 tests passing, strict Mypy clean on 120 files, Ruff lint & format clean, Next.js build clean.
- **Blocked / Incomplete**: Awaiting human approval for Phase 8 gate before proceeding to Phase 9 (Live Readiness).

## NEXT UP
1. [x] Phase 8 implementation & verification.
2. [ ] Human sign-off on Phase 8 gate.
3. [ ] Proceed to Phase 9 (Live Readiness).

## SESSION LOG
### 2026-08-23 — Session 13: Interactive Walkthrough Tour, In-App Documentation (/docs), and Universal Plain-English Tooltips
- Built interactive 6-step `WalkthroughModal` (`web/src/components/WalkthroughModal.tsx`) and `WalkthroughContext` (`web/src/components/WalkthroughContext.tsx`) covering system architecture, L1-L4 alpha layers, strategy immutability, the research loop & 8 gates, live/paper execution, and the operator playbook.
- Created comprehensive in-app Knowledge Base & Documentation dashboard (`web/src/app/docs/page.tsx`) with 9 interactive concept tabs.
- Expanded bilingual TypeScript i18n dictionaries in `web/src/i18n/types.ts`, `web/src/i18n/en.ts`, and `web/src/i18n/de.ts` with complete translations for all walkthrough slides, docs articles, and new tooltips.
- Conducted exhaustive audit across all pages (`Overview`, `Live`, `Versions`, `Compare`, `Signals`, `Models`, `Fundamentals`, `Narrative`, `Research`, `Run Detail`) adding plain-English beginner-friendly tooltips for all non-self-explanatory terms, table headers, blotter columns, and action buttons.
- Integrated `[ ⚡ Getting Started ]` tour trigger in the `Navigation` sidebar and `Overview` quick-orientation banner.
- Verified Next.js production build (`npm run build`) passing 100% cleanly across all 13 routes, all 212 pytest tests passing, strict Mypy clean on 120 files, Ruff clean, and Backend API (:8001) & Webapp (:3000) verified healthy and live.

### 2026-08-23 — Session 12: Comprehensive Component-by-Component i18n Translation & German Locale Enforcement
- Conducted exhaustive audit across all 10 pages and shared UI components (`ChartCanvas`, `Navigation`, `Overview`, `Live`, `Versions`, `Compare`, `Signals`, `Models`, `Fundamentals`, `Narrative`, `Research`, `Run Detail`).
- Expanded TypeScript translation definitions in `web/src/i18n/types.ts` and dictionary entries in `web/src/i18n/en.ts` and `web/src/i18n/de.ts` covering 100% of UI strings (modals, confirmation alerts, form placeholders, table headers, blotters, discovery modalities, promotion gates, axis labels, and tooltip descriptions).
- Refactored `ChartCanvas.tsx` to translate axis and bar labels (`MIN`, `MAX`, `BARS`, `Series`).
- Refactored `live/page.tsx` with bilingual support for bucket sub-account cards, emergency liquidation confirmation, kill-switch alert banners, and blotter columns.
- Refactored `versions/page.tsx` with translated table headers, filter options, lineage tree viewer, and tooltips.
- Refactored `compare/page.tsx` with bilingual metric definitions, equity/drawdown curve titles, and reproducibility metadata.
- Refactored `signals/page.tsx` with bilingual search placeholders, metric cards, subvalues, and indicator panel names.
- Refactored `models/page.tsx` with bilingual market regime quadrant names, telemetry values, and feature importance labels.
- Refactored `fundamentals/page.tsx` with bilingual PIT status, scorecards, blackout guard indicators, and screener table columns.
- Refactored `narrative/page.tsx` with bilingual LLM scoring sandbox form, sentiment profile cards, and structured evaluation fields.
- Refactored `research/page.tsx` with bilingual discovery modalities, 8-gate promotion matrix, hypothesis ledger, and holdout unlock modal.
- Refactored `runs/[id]/page.tsx` with bilingual reproducibility footer, trade blotter headers, and KPI cards.
- Verified Next.js production build (`npm run build`) passing 100% cleanly without errors or untyped keys. All 212 tests pass, strict Mypy clean on 120 files, Ruff clean.

### 2026-08-23 — Session 11: Phase 8 The Research Loop Complete
- Created Alembic migration `0006_phase8_research_loop.py` and SQLAlchemy models `ResearchHypothesis`, `ResearchSweep`, `ResearchReport`, and `HoldoutAccessLog`.
- Implemented `atlas/research/stats.py` with Deflated Sharpe Ratio (DSR), CSCV Probability of Backtest Overfitting (PBO), Monte Carlo trade permutation distributions, and walk-forward splits.
- Built `StatisticalGatekeeper` in `atlas/research/gatekeeper.py` automating all 8 promotion gates (§8.3) and detailed Markdown summary reports.
- Built `HoldoutGuard` in `atlas/research/holdout.py` strictly restricting automated fitting to Train (2005-2018) / Validation (2019-2022) partitions and requiring explicit human authorization to unlock holdout.
- Built `HypothesisGenerator` in `atlas/research/hypothesis.py` supporting parameter refinement, multi-layer feature exploration (L1-L4), regime conditioning, and genetic recombination.
- Built `SweepEngine` in `atlas/research/sweep.py` managing parameter grids and recording all multiple-testing iterations in the sacred `trials` ledger.
- Implemented `ResearchDaemon` in `atlas/research/daemon.py` orchestrating hypothesis formulation, sweeps, gatekeeper checks, out-of-sample validation, and report generation.
- Implemented FastAPI research router in `atlas/api/routers/research.py` and schemas in `atlas/api/schemas/research.py`.
- Built Next.js Research & Discovery view (`web/src/app/research/page.tsx`) with trial budget gauge, daemon telemetry, reports viewer, and 1-click Human Promotion Queue.
- Added complete bilingual English & German translations and plain-English tooltips for PBO, DSR, Walk-Forward, Monte Carlo, and Holdout Guard.
- Added 21 new unit, property (`hypothesis`), and overfitting rejection tests (212 total tests passing).
- Full verification clean: `ruff check`, `ruff format --check`, `mypy --strict` on 120 files, Next.js build (`npm run build`), and live verification of Backend API (`:8001`) and Webapp (`:3000`).

## SESSION LOG
### 2026-08-23 — Session 10: Complete Bilingual i18n Translation System (English & German)
- Built type-safe i18n translation framework in `web/src/i18n/` (`types.ts`, `en.ts`, `de.ts`, `LanguageContext.tsx`, `index.ts`) supporting instantaneous zero-reload language switching with `localStorage` persistence and English as default.
- Implemented `LanguageSwitch` component in `web/src/components/LanguageSwitch.tsx` with clean terminal-styled `[ EN | DE ]` toggle and integrated into `Navigation.tsx` sidebar.
- Translated 100% of strings across all 9 views and shared components: Navigation, Overview (`/`), Live / Paper Trading (`/live`), Versions & Lineage (`/versions`), Run Comparison (`/compare`), Signals Explorer (`/signals`), ML & Regimes (`/models`), Fundamentals & L3 (`/fundamentals`), Narrative & L4 (`/narrative`), and Run Details (`/runs/[id]`).
- All financial metrics, table headers, blotter columns, status indicators, and plain-English beginner tooltips translated in both German and English.
- Next.js production build (`npm run build`) and verification suite passing 100% cleanly.

### 2026-08-23 — Session 9: Phase 7 Narrative & LLM Signals (L4) Complete
- Created Alembic migration `0005_phase7_news_llm_signals.py` and SQLAlchemy models `NewsArticle`, `NewsScore`, and `PromptTemplate`.
- Implemented `AlpacaNewsProvider` in `atlas/data/providers/alpaca_news.py` and CLI command `atlas data ingest-news` in `atlas/data/cli.py`.
- Built LLM client, versioned prompt registry, and news scoring engine in `atlas/llm/` with structured JSON contract (`LLMNewsAnalysis`) and offline heuristic fallback mode.
- Integrated `news(symbol, lookback_hours)` into `MarketContext` and `HistoricalMarketContext`, strictly blocking lookahead (`published_at <= clock.now`).
- Enabled short selling for SWING bucket with 3% annual borrow cost in `DefaultCostModelV1`, short stop losses in `SimBroker`, short accounting in `BucketLedger`, and gross exposure risk limits in `HardLimitsValidator`.
- Implemented L4 signal providers `NewsSentimentSignalProvider` and `NarrativeMomentumSignalProvider` in `atlas/signals/l4_narrative.py` and registered in `atlas/strategies/builder.py`.
- Authored L4 specs: `core_narrative_l4.yaml` and `swing_narrative_l4.yaml`.
- Implemented FastAPI router in `atlas/api/routers/news.py` and schemas in `atlas/api/schemas/news.py`.
- Built Next.js Narrative & LLM view (`web/src/app/narrative/page.tsx`) and updated `Navigation.tsx` with `/narrative` route.
- Added 18 new unit, property (`hypothesis`), lookahead, and shorting verification tests (191 total tests passing).
- Full verification suite clean: `ruff check`, `ruff format --check`, `mypy --strict` on 111 files, `npm run build`, and live verification of Backend API (`:8001`) and Webapp (`:3000`).

## SESSION LOG
### 2026-08-23 — Session 8: Phase 6 Fundamentals & Valuation (L3) Complete
- Created Alembic migration `0004_phase6_fundamentals_earnings.py` and SQLAlchemy models `FundamentalFiling` and `EarningsEvent`.
- Implemented `FMPProvider` in `atlas/data/providers/fmp.py` supporting income statements, balance sheets, cash flows, key metrics, and historical/upcoming earnings calendars with strict SEC filing timestamp parsing.
- Integrated `fundamentals(symbol)` and `upcoming_earnings(symbol, lookahead_days)` into `MarketContext` and `HistoricalMarketContext`, strictly blocking lookahead (`filing_date <= clock.now`).
- Implemented `FundamentalFeatureExtractor` and `SectorRelativeNormalizer` in `atlas/signals/features/fundamental.py` with Sloan accruals, ROIC, FCF yield, EV/EBITDA, and sector peer z-score normalization.
- Implemented L3 signal providers `ValuationQualitySignalProvider` and `EarningsSurpriseSignalProvider` in `atlas/signals/l3_fundamental.py` and registered in `atlas/strategies/builder.py`.
- Implemented `EarningsBlackoutGuard` in `atlas/risk/blackout.py` preventing high-beta/MOONSHOT entries 2 days pre-earnings.
- Authored L3 specs: `core_trend_l3.yaml` and `swing_meanrev_l3.yaml`.
- Implemented FastAPI router in `atlas/api/routers/fundamentals.py` and schemas in `atlas/api/schemas/fundamentals.py`.
- Built Next.js Fundamentals & Valuation view (`web/src/app/fundamentals/page.tsx`) and updated `Navigation.tsx` with `/fundamentals` route.
- Added 13 new unit, property (`hypothesis`), and lookahead verification tests (173 total tests passing, 78.1% overall coverage).
- Full verification suite clean: `ruff check`, `ruff format --check`, `mypy --strict` on 103 files, `npm run build`, and live verification of Backend API (`:8001`) and Webapp (`:3000`).

## SESSION LOG
### 2026-08-23 — Session 7: Phase 5 Statistical & ML Signals (L2) Complete
- Implemented `StatisticalFeatureExtractor` with 20 statistical features (Garman-Klass, Parkinson vol, normalized ATR, MACD z-score, Bollinger %b, RSI 14/2, 52w range, volume z-scores).
- Implemented `CrossSectionalRanker` and `MarketBreadthCalculator`.
- Implemented `FeatureEngine` managing batch dataset creation and Parquet feature snapshot persistence.
- Implemented 4-quadrant `RegimeDetector` (`BULL_LOW_VOL`, `BULL_HIGH_VOL`, `BEAR_HIGH_VOL`, `BEAR_LOW_VOL`, `SIDEWAYS_NORMAL`).
- Implemented `PurgedKFoldCV` with embargo quarantine windows preventing lookahead and serial correlation leakage.
- Implemented `MLTrainer` and `ShapExplainer` for LightGBM model training with SHAP local feature attributions populated directly into `Signal.rationale`.
- Built `ModelRegistry` and bootstrapped default baseline model artifact (`lgbm_dir_5d_v1` v1.0.0).
- Implemented L2 signal providers in `atlas/signals/l2_statistical.py` (`CrossSectionalMomentumProvider`, `MarketRegimeSignalProvider`, `LightGBMSignalProvider`) and registered them in strategy builder.
- Authored L2 strategy specs: `core_trend_l2.yaml` and `swing_meanrev_l2.yaml`.
- Implemented FastAPI router in `atlas/api/routers/models.py` for model registry, prediction with SHAP explanations, and live regime classification.
- Built Next.js ML & Regimes dashboard (`web/src/app/models/page.tsx`) with real-time regime telemetry, model registry browser, CV performance metrics, feature importance bars, and plain-English tooltips.
- Added 20 new tests (160 total passing, 79.2% overall coverage).
- Full verification suite clean: `ruff check`, `ruff format --check`, `mypy --strict` on 97 files, `npm run build`, and live verification of Backend API (`:8001`) and Webapp (`:3000`).
