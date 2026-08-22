# ATLAS — Autonomous Trading & Learning Analysis System

ATLAS is an autonomous equity trading system designed to discover, validate, and execute quantitative trading strategies with strict statistical validation, zero lookahead bias, and multi-layer risk controls.

## Requirements
- Python 3.12 (`uv`)
- Docker & Docker Compose
- Node.js 20+ (for web UI)

## Quickstart Setup
1. Copy `.env.example` to `.env`:
   ```bash
   cp .env.example .env
   ```
2. Initialize virtual environment and install dependencies:
   ```bash
   uv venv --python 3.12
   uv sync --all-extras
   ```
3. Start infrastructure services (PostgreSQL + TimescaleDB, Redis):
   ```bash
   make up
   ```
4. Run verification suite:
   ```bash
   make check
   ```
5. Run API server:
   ```bash
   make dev
   ```

## Development Commands
- `make check` — Run linter, formatter check, type check, and tests.
- `make test` / `make test-fast` / `make cov` — Run test suite with pytest.
- `make lint` / `make fmt` / `make typecheck` — Ruff linting & Mypy strict type checking.
- `make up` / `make down` / `make logs` — Docker compose lifecycle.

## Documentation
- `docs/MASTER_PLAN.md` — Master specification and technical blueprint.
- `docs/ARCHITECTURE.md` — Component architecture and diagrams.
- `docs/DATA_CONTRACTS.md` — Core domain types and database schemas.
- `docs/RISK_FRAMEWORK.md` — Portfolio buckets, risk limits, and kill switches.
- `docs/VALIDATION_PROTOCOL.md` — Statistical testing and promotion gates.
- `docs/ROADMAP.md` — Phase progression roadmap.
- `AGENTS.md` — Operating rules for AI development sessions.
