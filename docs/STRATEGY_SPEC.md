# ATLAS — Strategy Specification

A strategy version is defined by a **YAML spec + referenced code modules**. The spec's SHA-256 hash is its identity.

```yaml
# strategies/core_trend_v1.yaml
id: core_trend
version: 1
bucket: CORE
description: >
  Dual-momentum on liquid ETFs with a long-term regime filter.
  Baseline for the CORE bucket.

universe:
  source: etf_liquid
  filters: { min_adv_usd: 20_000_000, min_price: 5 }

resolution: 1d
rebalance: { schedule: "monthly_last_trading_day", time: "15:45 America/New_York" }

signals:
  - provider: l1.momentum
    weight: 0.6
    params: { lookback: 252, skip: 21 }
  - provider: l1.trend_filter
    weight: 0.4
    params: { ma_period: 200, ma_type: sma }

aggregator: { type: weighted_confidence, min_confidence: 0.3 }

policy:
  type: top_n_long_only
  params: { n: 5, min_score: 0.2, equal_weight: false, weight_by: inverse_vol }

risk:
  max_position_pct_of_bucket: 20
  stop_loss: { type: atr_trailing, atr_period: 14, multiple: 3.0 }
  take_profit: null
  max_holding_days: null

costs: { model: default_v1 }
```

## Versioning Rules
- Changing any parameter requires creating a new version.
- Spec status lifecycle: `RESEARCH -> CANDIDATE -> PAPER -> SHADOW -> LIVE -> RETIRED`.
- Changing provider code without bumping its version hash is a build error.

## Signal Aggregation
```
composite = Σ(w_i * score_i * confidence_i) / Σ(w_i * confidence_i)
```
If total confidence is below `min_confidence`, the symbol is skipped. Abstention is a valid output.

## Position Policies
- `top_n_long_only`: Rank by composite score, select top N above score threshold.
- `threshold_long_only`: Enter above `+t`, exit below `-t` (hysteresis band).
- `target_weight`: Composite score maps linearly to target portfolio weight.
- `event_burst`: Moonshot entry on signal spike, hard time + price stop.
