# ATLAS — Phase Roadmap

Each phase is executed on a dedicated branch (`phase-N/slug`), squashed to `main`, and tagged `phase-N-complete`. No phase advances without passing its gate.

---

### PHASE 0 — Foundation
- **Scope:** Repo scaffolding, `uv`, package skeleton, core frozen types (`Money` strictly rejecting float), FastAPI `/health` + `/version`, Docker compose (TimescaleDB, Redis, API stub), Alembic baseline, Makefile, tests.
- **Gate:** `make up` healthy, `make test lint typecheck` clean.

---

### PHASE 1 — Data Foundation
- **Scope:** Trading calendar, provider clients (Tiingo, Alpaca, yfinance) with rate limiting & retry, TimescaleDB schema + migrations, universe builder (point-in-time), corporate actions, validator checks, Parquet snapshot writer, CLI tools.
- **Gate:** 2005->today bars for ~540 symbols ingested, zero CRITICAL health issues, byte-identical snapshot reproduction.

---

### PHASE 2 — Engine & Baselines
- **Scope:** `Clock` (Sim/Real), `MarketContext` with `LookaheadError`, event loop, `SimBroker`, `costs.default_v1`, metrics module, L1 technical signal library, aggregator, 3 position policies, YAML spec loader, baselines (`core_trend_v1`, `swing_meanrev_v1`, `buy_hold_spy`).
- **Gate:** Lookahead test suite passes clean, deterministic backtest replay, benchmark returns verified.

---

### PHASE 3 — Versioning & Dashboard v1
- **Scope:** Strategy version registry, run registry with reproducibility metadata, trial counter, API endpoints (`/versions`, `/runs`, `/compare`), Next.js dashboard views.
- **Gate:** Spec mutation protection verified, compare view active, run reproducibility verified.

---

### PHASE 4 — Portfolio, Risk & Paper Trading
- **Scope:** Bucket ledger with isolated accounts, position sizing, hard limits, kill switches, `AlpacaPaperBroker`, live runner daemon (APScheduler), state persistence & recovery, WebSocket streaming, alerting.
- **Gate:** 14 consecutive days autonomous paper trading, crash recovery verified, all kill switches tested.

---

### PHASE 5 — Statistical & ML Signals (L2)
- **Scope:** Feature store, regime detection, cross-sectional ranking, LightGBM models with purged CV, SHAP explainability.
- **Gate:** L2 version beats Phase 2 baseline out-of-sample or documented negative-result ADR.

---

### PHASE 6 — Fundamentals & Valuation (L3)
- **Scope:** FMP ingestion with strict filing-date PIT discipline, valuation/quality/growth features, earnings blackout rules.
- **Gate:** Drawdown reduction / Calmar improvement or negative-result ADR.

---

### PHASE 7 — Narrative & LLM Signals (L4)
- **Scope:** News ingestion & deduplication, local LLM scoring via vLLM/llama-swap (structured JSON), prompt versioning, shorting enabled for SWING.
- **Gate:** Positive out-of-sample edge on validation, $<5s$ p95 latency, zero lookahead.

---

### PHASE 8 — The Research Loop
- **Scope:** Autonomous research daemon (hypothesis -> sweep -> gatekeeper -> validate -> report -> human queue -> trial counter).
- **Gate:** Runs unattended for 7 days, generates $\ge 3$ research reports, correctly rejects overfit strategies.

---

### PHASE 9 — Live Readiness
- **Scope:** `IBKRBroker`, shadow execution mode, live/shadow divergence monitor, reconciliation, TOTP 2FA, German tax reporting, production deployment.
- **Gate:** All promotion gates met, manual human unlock required.
