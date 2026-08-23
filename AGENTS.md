# ATLAS — Agent Operating Rules

You are building ATLAS, an autonomous equity trading system.
`docs/MASTER_PLAN.md` is authoritative. This file governs how you work.

## Session Protocol
1. Read `notes.md` / `docs/working_notes.md` FIRST (current state of the system).
2. Read active phase in `docs/ROADMAP.md` (or `docs/MASTER_PLAN.md` §11). Identify next open task.
3. State your plan for the session BEFORE writing code. Wait for confirmation.
4. Work on ONE task at a time (small, verifiable, committed).
5. Before ending: update `notes.md` & `docs/working_notes.md`, run `make check`, build and start/verify that both Backend API (`:8001`) and Webapp (`:3000`) are up and running at the latest version for interactive testing, and commit.
6. NEVER begin a new phase without explicit human approval.

## Common Developer Commands
- `make check` — Run full verification suite (`lint` + `format-check` + `typecheck` + `test` + `web build`). Agent must run this before finishing.
- `make dev` — Hot-reload API + Web + Runner.
- `make up` / `make down` / `make logs` — Docker Compose lifecycle.
- `make test` / `make test-fast` / `make cov` — Run pytest test suite.
- `make lint` / `make fmt` / `make typecheck` — Ruff linting/formatting and mypy strict typechecking.
- `make migrate` / `make migration name=<slug>` — Alembic migrations.
- `make backtest spec=strategies/<spec>.yaml` — Run backtest on strategy specification.

## Hard Invariants (Violating any is a critical bug)
1. **NO LOOKAHEAD:** Signals access data ONLY via `MarketContext`, which strictly filters `timestamp <= clock.now`. Never bypass or create escape hatches.
2. **PARITY:** Backtest, paper, and live modes execute identical signal, aggregator, policy, risk, and OMS code. Only `Clock` (`SimClock` vs `RealClock`) and `Broker` (`SimBroker` vs `AlpacaPaperBroker` / `IBKRBroker`) differ.
3. **DECIMAL MONEY:** All monetary calculations use `Money` wrapping `Decimal`. Floats are strictly prohibited in financial arithmetic and raise `TypeError`.
4. **TIMEZONES:** All timestamps must be timezone-aware UTC internally. UI display defaults to `Europe/Berlin`.
5. **STRATEGY IMMUTABILITY:** Strategy YAML specs are immutable once referenced by a `Run`. Changes require creating a new version with `parent_id` set.
6. **CENTRALIZED RISK:** Risk limits and kill switches live ONLY in `atlas/risk/`. Strategies never enforce their own risk limits.
7. **FILL TIMING:** Fills occur on the bar AFTER the decision bar (`t+1`). Never fill at same-bar close.
8. **RUN REPRODUCIBILITY:** Every `Run` record must store `git_sha`, `spec_hash`, `data_snapshot_id`, `seed`, `lib_versions`, and `cost_model_hash`.
9. **SECRETS & CONFIG:** No hardcoded secrets or API keys in code, specs, or notebooks. Use `.env` only.
10. **NOTEBOOKS ISOLATION:** `notebooks/` is for ad-hoc experimentation and must never be imported by `atlas/`.
11. **NO LIVE TRADING:** `ATLAS_ALLOW_LIVE` remains `false`. Never write code that enables live execution or bypasses live safety guards.
12. **RECORD NEGATIVE RESULTS:** Failed backtests and negative results are valuable. Record every trial in the `trials` table; never silently tune parameters without trial incrementing.
13. **ALWAYS RUNNING & TESTABLE:** The backend engine API (`http://localhost:8001`) and webapp dashboard (`http://localhost:3000`) must always be launched and verified running after every step/phase so the user can immediately test the solution.
14. **PLAIN-LANGUAGE UI TOOLTIPS:** All UI metrics, indicators, and system invariants must provide concise, beginner-friendly tooltips explaining what they mean in plain English (e.g., RSI 14, 200 SMA, Parity, Lookahead, CAGR, Sharpe) so any user has instant clarity.

## Definition of Done
- [ ] Strict type hints (`mypy --strict` passes clean on `core/`, `risk/`, `portfolio/`, `backtest/`, `execution/`).
- [ ] Tests passing with coverage: >= 85% in `risk/`, `portfolio/`, `backtest/`, `core/`; >= 70% elsewhere.
- [ ] Property-based tests (`hypothesis`) for arithmetic on money, quantities, or weights.
- [ ] `ruff check` and `ruff format` clean.
- [ ] Documentation updated for any schema, contract, or interface change.
- [ ] Both Backend API (`:8001`) and Webapp (`:3000`) built, running live at the latest version, and verified testable.
- [ ] Non-obvious UI metrics, indicators, and system terms equipped with plain-English tooltips.
- [ ] `notes.md` and `docs/working_notes.md` updated with current state, next tasks, and session log entry.
- [ ] Conventional Commit referencing the phase (`phase-N/slug`).

## Architecture & Conventions
- **Stack:** Python 3.12 (`uv`), PostgreSQL 16 + TimescaleDB, DuckDB / Parquet snapshots, Redis 7, FastAPI + Pydantic v2, Next.js 15 App Router.
- **Architectural Decisions:** Any structural deviation, schema change, or new dependency requires an ADR in `docs/decisions/ADR-XXXX-slug.md`.
- **Holdout Partition (2023-01-01 -> present-90d):** Strictly locked; requires explicit human unlock via CLI. Never evaluate against holdout during research/fitting.
- **Do not mix changes:** Keep `atlas/` (backend/engine) and `web/` (frontend) changes in separate commits.
