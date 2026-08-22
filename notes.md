# ATLAS — Engineering Notes & Session Log

## CURRENT STATE
- **Phase**: 1 (Data Foundation) — Completed & Verified
- **Active Branch**: `phase-1/data-foundation`
- **Current Milestone**: Market data layer, database schema & migrations, provider clients (Tiingo, Alpaca, yfinance), normalization, corporate actions adjustments, §4.5 validation engine, point-in-time universe builder, byte-reproducible Parquet snapshot manager, and data CLI commands.
- **Working Components**:
  - `atlas.data.models`: SQLAlchemy 2.0 models (`Instrument`, `UniverseSnapshot`, `Bar1D`, `CorporateAction`, `DataHealth`).
  - `migrations/versions/0001_phase1_data_schema.py`: Alembic migration for the data layer schema.
  - `atlas.data.providers`: Asynchronous provider clients with token-bucket rate limiting, exponential backoff with jitter, local disk caching, and healthchecks (`TiingoProvider`, `AlpacaMarketDataProvider`, `YFinanceProvider`).
  - `atlas.data.normalize`: Normalization pipeline converting vendor formats to domain `Bar` objects and continuous backward corporate action adjustments.
  - `atlas.data.validate`: Validation engine enforcing all §4.5 invariant checks (bounds, calendar completeness, zero volume, price jumps, cross-source divergence).
  - `atlas.data.universe`: Point-in-time universe filtering preventing survivorship bias.
  - `atlas.data.snapshots`: Deterministic, byte-reproducible Parquet snapshot generator and reader with SHA-256 tracking.
  - `atlas.data.ingest` & `atlas.data.cli`: Pipeline and CLI subcommands (`ingest`, `snapshot`, `coverage`).
  - `tests`: 76 unit and hypothesis tests, 80.6% code coverage, 100% clean strict mypy & ruff.
- **Blocked / Incomplete**: Next phase: Phase 2 (Engine & Baselines).

## NEXT UP
1. [x] Phase 1 implementation & verification.
2. [ ] Commit Phase 1 changes to `phase-1/data-foundation`.
3. [ ] Await human gate review for Phase 1 before starting Phase 2.

## OPEN QUESTIONS & DECISIONS
- Primary provider: Tiingo API for EOD historical bars and corporate actions.
- Secondary provider: Alpaca Data v2 for cross-source validation.
- Fallback provider: yfinance.

## SESSION LOG
### 2026-08-23 — Session 2: Phase 1 Data Foundation Complete
- Implemented `atlas.data` module structure and database models.
- Added Alembic migration `0001_phase1_data_schema.py`.
- Implemented provider clients (`TiingoProvider`, `AlpacaMarketDataProvider`, `YFinanceProvider`, `BaseDataProvider`).
- Built corporate action adjustment calculations, data validation engine, PIT universe builder, snapshot manager, and CLI.
- Added comprehensive unit tests and hypothesis property tests.
- Verified test suite and type safety (`mypy --strict`, `ruff`, `pytest`).
