# ATLAS — Engineering Notes & Session Log

## CURRENT STATE
- **Phase**: 0 (Foundation) — Completed & Verified
- **Active Branch**: `phase-0/foundation`
- **Current Milestone**: Repository scaffolding, documentation modularization, ADR-0001, core type system with strict Money, FastAPI health/version endpoints, test suite, and Docker infrastructure.
- **Working Components**:
  - `atlas.core.money.Money`: Wrapped `Decimal` arithmetic with strict float rejection (TypeError) and internal 4dp quantization.
  - `atlas.core.types`: Frozen domain dataclasses (`Bar`, `Signal`, `Order`, `Fill`, `Position`, `AccountState`, etc.).
  - `atlas.core.clock`: `SimClock` and `RealClock` implementations ensuring UTC awareness.
  - `atlas.core.context`: `MarketContext` protocol & base class guarding against lookahead.
  - `atlas.core.config`: Pydantic settings with safety validation (leverage hard cap $\le 1.0$, `allow_live=False`).
  - `atlas.core.logging`: JSON and formatted console logging.
  - `atlas.core.calendar`: NYSE (`XNYS`) calendar integration.
  - `atlas.api`: FastAPI app with `/health` and `/version` endpoints and WebSocket hub.
  - `tests`: 46 tests (unit + property-based `hypothesis` tests), 93.1% code coverage, 100% clean strict mypy & ruff.
- **Blocked / Incomplete**: Next phase: Phase 1 (Data Foundation).

## NEXT UP
1. [x] Phase 0 implementation & verification.
2. [ ] Commit Phase 0 changes to `phase-0/foundation`.
3. [ ] Await human gate review for Phase 0 before starting Phase 1.

## OPEN QUESTIONS & DECISIONS
- Data Providers: Tiingo API key configured; Alpaca integration planned for Phase 1.
- Local LLM endpoint configured (`http://192.168.0.149:8080/v1`) for Phase 7.

## SESSION LOG
### 2026-08-23 — Session 1: Phase 0 Foundation Complete
- Split `base_documentation_v1.md` into `docs/` (`MASTER_PLAN.md`, `ARCHITECTURE.md`, `DATA_CONTRACTS.md`, `STRATEGY_SPEC.md`, `RISK_FRAMEWORK.md`, `VALIDATION_PROTOCOL.md`, `ROADMAP.md`).
- Authored `docs/decisions/ADR-0001-initial-stack.md` capturing locked decisions D1–D20.
- Created `pyproject.toml`, `.gitignore`, `Makefile`, and `compose.yml` (TimescaleDB + Redis).
- Implemented `atlas.core` modules and `atlas.api` service.
- Implemented unit and hypothesis property tests with 93.1% coverage.
- Validated all linters, type checks, and test suites (`ruff`, `mypy --strict`, `pytest`).
