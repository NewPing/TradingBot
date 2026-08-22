# ATLAS — Portfolio & Risk Framework

## 6.1 Buckets (Independent Sub-Portfolios)

| Bucket | Target Alloc | Rebalance Band | Horizon | Instruments | Max Positions | Max Single Pos | Stop Policy |
|---|---|---|---|---|---|---|---|
| **CORE** | 50% | ±5pp | 1–12 months | Liquid ETFs, mega-cap | 8 | 20% of bucket | ATR-trailing 3x or regime exit |
| **SWING** | 30% | ±5pp | 2–20 days | S&P 500 liquid | 12 | 10% of bucket | ATR 2x + 20-day time stop |
| **MOONSHOT** | 15% | ±3pp | hours–5 days | High-ADV high-vol | 6 | 2.5% of bucket | Hard -25% stop, 5-day time stop |
| **CASH** | 5% | — | — | — | — | — | — |

Buckets maintain separate cash accounts in the internal ledger. No inter-bucket borrowing.

## 6.2 Position Sizing

```
target_vol_per_position = bucket_vol_budget / expected_n_positions
raw_weight   = target_vol_per_position / realized_vol_20d(symbol)
conviction   = clip(|composite_score|, 0.3, 1.0)
weight       = min(raw_weight * conviction, max_position_pct_of_bucket)
qty          = floor(weight * bucket_equity / price)
```

- Annualized Vol Budgets: CORE 10%, SWING 15%, MOONSHOT 35%.
- Portfolio Gross Exposure Cap: 100%. No fractional shares in Phase $\le 4$.

## 6.3 Hard Limits (Risk Manager Rejection Rules)
- Gross exposure $\le 100\%$ of equity.
- Single symbol $\le 10\%$ of total equity across all buckets combined.
- Single sector $\le 30\%$ of total equity.
- Correlation guard: no new position with 60-day correlation $> 0.85$ to an existing position in same bucket.
- Order notional $\le 1\%$ of symbol 20-day ADV.
- Max 20 orders per day per bucket.
- No new entries in last 10 minutes of trading session.
- No entries when `data_health` has unresolved `CRITICAL` for symbol.

## 6.4 Kill Switches

| Trigger | Threshold | Action | Reset |
|---|---|---|---|
| Daily loss | -2% of total equity | Halt new entries for session; stops active | Automatic next session |
| Rolling 5-day loss | -5% | Halt all entries | **Human** |
| Drawdown from peak | -15% | Flatten MOONSHOT, halt all entries | **Human** |
| Drawdown from peak | -25% | Flatten everything, full stop | **Human + post-mortem ADR** |
| Data staleness | > 2 expected bars | Halt entries, alert | Automatic on recovery |
| Broker disconnect | > 60s | Cancel working orders, halt | Automatic + reconciliation |
| Order reject rate | > 20% over 10 orders | Halt bucket | **Human** |
| Live/shadow divergence | > 0.5% equity over 5 days | Halt, alert | **Human** |
| Unhandled loop exception | Any | Halt, alert, persist state | **Human** |
