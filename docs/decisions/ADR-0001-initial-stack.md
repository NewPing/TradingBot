# ADR-0001: Initial Architecture and Technical Stack Decisions

- **Status**: Accepted
- **Date**: 2026-08-23
- **Author**: Jan & AI Assistant
- **Scope**: Foundation & Core Architecture

## Context
ATLAS requires a robust, reproducible, and strictly disciplined software architecture capable of transitioning trading strategies from research to simulated execution and eventually to live capital, while completely preventing lookahead bias, unhandled risk, and floating-point financial bugs.

## Decisions (Locked D1–D20)

1. **D1 - Asset Universe**: US-listed equities + ETFs only (single currency, single session, high data quality).
2. **D2 - Tradable Universe**: S&P 500 constituents + ~40 liquid ETFs, filtered to ADV > $20M and price > $5.
3. **D3 - Primary Resolution**: Daily adjusted bars.
4. **D4 - Secondary Resolution**: 1-hour from Phase 4; 1-minute for Moonshot from Phase 7.
5. **D5 - History Depth**: Daily from 2005-01-01 onwards (covers 2008, 2020, 2022 market crises).
6. **D6 - Data Providers**: Tiingo (primary daily adjusted), Alpaca (intraday + paper execution), yfinance (bootstrap/dev only), FMP (fundamentals).
7. **D7 - Language / Runtime**: Python 3.12 managed with `uv`.
8. **D8 - Databases**: PostgreSQL 16 + TimescaleDB (system of record), DuckDB / Parquet (backtesting hot path), Redis 7 (queue/bus/cache).
9. **D9 - API**: FastAPI + Pydantic v2 with strict schemas and auto-generated OpenAPI.
10. **D10 - Frontend**: Next.js 15 App Router + TypeScript + Tailwind CSS + shadcn/ui + TanStack Query + uPlot + Recharts.
11. **D11 - Deployment**: Docker Compose with profiles (`research` for Unraid compute, `live` for always-on server).
12. **D12 - Compute Split**: Local GPU compute (2x 3090s) for sweeps/ML/LLM; server for execution/daemon/API.
13. **D13 - Broker Abstraction**: `Broker` protocol with `SimBroker`, `AlpacaPaperBroker`, and `IBKRBroker` implementations.
14. **D14 - Starting Capital**: $100,000 virtual USD baseline.
15. **D15 - Currency / Accounting**: Internal accounting strictly in USD using `Decimal` (`Money` type). Floats forbidden.
16. **D16 - Timezones**: All internal timestamps in timezone-aware UTC; display in `Europe/Berlin`; exchange calendar XNYS.
17. **D17 - Shorting**: Long/flat only through Phase 6; shorting enabled in Phase 7 for Swing bucket.
18. **D18 - Leverage**: 1.0x hard cap enforced by Risk Manager.
19. **D20 - Git Strategy**: Trunk-based workflow, feature branch per phase (`phase-N/slug`), Conventional Commits, squash-merge to main, tag `phase-N-complete`.

## Consequences
- Strict compliance with `Money` type everywhere.
- No lookahead bias possible due to `MarketContext` gate.
- Full parity between backtest, paper, and live code.
