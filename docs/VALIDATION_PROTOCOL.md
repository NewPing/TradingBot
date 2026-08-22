# ATLAS — Backtesting & Validation Protocol

## 8.1 Engine Execution Loop
1. Single-threaded event loop over trading calendar days.
2. Decisions at bar `t` use data strictly up to `t` via `MarketContext`.
3. Fills process on bar `t+1`.

## 8.3 Data Partitions

| Partition | Date Range | Access Rules |
|---|---|---|
| **Train** | 2005-01-01 -> 2018-12-31 | Unlimited access. Strategy optimization occurs here. |
| **Validation** | 2019-01-01 -> 2022-12-31 | Unlimited reads; every evaluation increments the trial counter. |
| **Holdout** | 2023-01-01 -> present-90d | **Strictly locked.** Requires CLI unlock (`atlas holdout unlock --family X --reason "..."`). |
| **Live-forward** | present-90d -> present | Paper trading only. Never used for fitting. |

## Candidate Promotion Requirements (8 Gates)
1. **Walk-forward**: rolling 3y train / 1y test, $\ge 6$ folds. Median fold Sharpe $> 0.5$.
2. **Parameter robustness**: $\pm 25\%$ perturbation on every parameter -> Sharpe degradation $< 40\%$.
3. **Monte Carlo trade shuffle** (1000 iterations): 5th-percentile CAGR $> 0$.
4. **Cost stress**: slippage $k = 1.0 \to 1.5$ -> Sharpe still $> 0.4$.
5. **Regime breakdown**: not net-negative in more than 1 of 4 regimes.
6. **Minimum sample**: $\ge 100$ trades and $\ge 3$ years of test data.
7. **PBO & Deflated Sharpe**: PBO $< 0.5$, Deflated Sharpe $> 0$.
8. **Correlation guard**: Correlation to existing PAPER/LIVE strategies $< 0.6$.

## Promotion Gates

| Stage | Gate Requirement |
|---|---|
| `RESEARCH -> CANDIDATE` | Passes all 8 validation tests + generated report + human approval |
| `CANDIDATE -> PAPER` | Holdout evaluation passed: Sharpe $> 0.5$, max DD $< 20\%$, $\ge 50$ trades |
| `PAPER -> SHADOW` | 90 consecutive days paper trading; Realized Sharpe $\ge 60\%$ of backtest Sharpe; zero unhandled errors |
| `SHADOW -> LIVE` | 60 days shadow mode with $\$0$ capital; fill price divergence $< 0.15\%$ |
| `LIVE` (small) | Starts at 5% capital; doubles every 30 days if metrics stay within tolerance |
