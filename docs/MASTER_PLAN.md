# ATLAS — Autonomous Trading & Learning Analysis System
### Master Plan & Technical Documentation · v1.0

This document is the master index and authoritative specification for ATLAS. All decisions are locked unless amended by an ADR in `docs/decisions/`.

---

## Table of Contents
1. [Charter](MASTER_PLAN.md#1-charter)
2. [Locked Decisions](decisions/ADR-0001-initial-stack.md)
3. [System Architecture](ARCHITECTURE.md)
4. [Data Contracts & Storage](DATA_CONTRACTS.md)
5. [Strategy Specification](STRATEGY_SPEC.md)
6. [Portfolio & Risk Framework](RISK_FRAMEWORK.md)
7. [Cost Model](DATA_CONTRACTS.md#cost-model)
8. [Backtesting & Validation Protocol](VALIDATION_PROTOCOL.md)
9. [Promotion Gates](VALIDATION_PROTOCOL.md#promotion-gates)
10. [Web Dashboard Specification & Color System](ARCHITECTURE.md#web-dashboard-specification)
11. [Phase Roadmap](ROADMAP.md)
12. [Agent Operating Rules](../AGENTS.md)
13. [Working Notes](working_notes.md)
14. [decisions/ (ADRs)](decisions/)

---

## 1. Charter

**Mission.** Build a self-hosted, autonomous equity trading system that discovers, validates, and executes trading strategies — starting entirely on simulated capital, with a rigorous, evidence-based promotion path toward real money.

**Non-negotiable principles.**
1. **Trust is earned by measurement.** No strategy touches capital without passing statistical gates defined in `docs/VALIDATION_PROTOCOL.md`.
2. **Backtest and live run the same code.** Divergence between simulation and reality is treated as a critical bug.
3. **Capital preservation outranks returns.** A strategy with lower returns and lower drawdown wins.
4. **The system is honest about failure.** Rejected strategies are recorded, not deleted. Negative results are results.
5. **The bot runs headless.** The web UI is a read-mostly observability layer. Killing the browser must never affect trading.

**Explicit anti-goals.** High-frequency trading. Leverage above 1.0×. Options, futures, crypto, FX. Market making. Anything requiring sub-second latency.

**Project name & namespace.** `atlas`. Python package `atlas`, DB `atlas`, Docker project `atlas`.
