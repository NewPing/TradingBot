"use client";

import { useState } from "react";
import { useTranslation } from "@/i18n";
import { InfoTooltip } from "@/components/Tooltip";
import {
  Layers,
  Sparkles,
  Calculator,
  ShieldCheck,
  TrendingUp,
  Cpu,
  FileText,
  Activity,
  CheckCircle2,
  ChevronDown,
  ChevronUp,
} from "lucide-react";

export function StrategyBlueprint({ strategyVersionId }: { strategyVersionId?: string }) {
  const { t } = useTranslation();
  const [activeTab, setActiveTab] = useState<"stack" | "formulas" | "phases" | "models">("stack");
  const [expandedFormula, setExpandedFormula] = useState<string | null>("momentum");

  const formulas = [
    {
      id: "momentum",
      layer: "L2 Statistical",
      name: "12-1 Month Cross-Sectional Momentum",
      math: "MOM_{12-1}(i) = \\frac{P_{t-21}(i)}{P_{t-252}(i)} - 1",
      plainFormula: "Momentum = (Price[t - 21 days] / Price[t - 252 days]) - 1",
      description:
        "Measures 12-month relative price performance while skipping the most recent 1 month (21 trading days) to eliminate short-term reversal noise.",
      variables: [
        { name: "P_{t-21}", desc: "Share price 21 trading days (~1 month) ago" },
        { name: "P_{t-252}", desc: "Share price 252 trading days (~12 months) ago" },
      ],
      insight: "Stocks ranking in the top decile exhibit persistent medium-term outperformance over 3-6 month holding horizons.",
    },
    {
      id: "rsi",
      layer: "L1 Technical",
      name: "Relative Strength Index (RSI 14 / RSI 2)",
      math: "RSI = 100 - \\left( \\frac{100}{1 + \\frac{EMA(Gains, N)}{EMA(Losses, N)}} \\right)",
      plainFormula: "RSI = 100 - (100 / (1 + Average_Gains / Average_Losses))",
      description:
        "Oscillator measuring the speed and change of price movements. Values < 30 (or < 10 for RSI 2) indicate oversold pullbacks ripe for mean-reversion entries.",
      variables: [
        { name: "EMA(Gains, N)", desc: "Exponential moving average of upward price changes over N periods" },
        { name: "EMA(Losses, N)", desc: "Exponential moving average of downward price changes over N periods" },
      ],
      insight: "Used as a timing trigger to enter established 200 SMA uptrends during temporary pullbacks.",
    },
    {
      id: "atr_stop",
      layer: "L1 Technical / Risk",
      name: "3x ATR Volatility-Adjusted Trailing Stop",
      math: "StopPrice_t = PeakPrice_t - (3.0 \\times ATR_{14})",
      plainFormula: "Stop Price = Highest High since Entry - (3.0 * ATR 14)",
      description:
        "Dynamic trailing stop loss that adapts automatically to each asset's realized volatility. Expands during volatile swings and tightens during quiet consolidations.",
      variables: [
        { name: "PeakPrice_t", desc: "Highest recorded execution price reached during trade lifecycle" },
        { name: "ATR_{14}", desc: "14-day Average True Range (TR = max[H-L, |H-C_prev|, |L-C_prev|])" },
      ],
      insight: "Prevents premature shakeouts on noisy high-beta stocks while locking in gains as trends mature.",
    },
    {
      id: "sloan_accrual",
      layer: "L3 Fundamental",
      name: "Sloan Accrual Ratio (Earnings Quality)",
      math: "AccrualRatio = \\frac{NetIncome - OperatingCashFlow}{TotalAssets}",
      plainFormula: "Accrual Ratio = (Net Income - Operating Cash Flow) / Total Assets",
      description:
        "Evaluates whether corporate earnings are backed by hard cash flow or aggressive non-cash accounting accruals. Values > 0.05 flag high probability of future earnings restatements.",
      variables: [
        { name: "NetIncome", desc: "Reported GAAP net income from SEC 10-K/10-Q filing" },
        { name: "OperatingCashFlow", desc: "Cash generated directly from core business operations" },
        { name: "TotalAssets", desc: "Average total assets across the reporting period" },
      ],
      insight: "Low-accrual companies systematically outperform high-accrual companies due to high earnings sustainability.",
    },
    {
      id: "roic",
      layer: "L3 Fundamental",
      name: "Return on Invested Capital (ROIC)",
      math: "ROIC = \\frac{NOPAT}{InvestedCapital} = \\frac{OperatingIncome \\times (1 - TaxRate)}{TotalDebt + TotalEquity - Cash}",
      plainFormula: "ROIC = (Operating Income * (1 - Tax Rate)) / (Debt + Equity - Cash)",
      description:
        "Measures how efficiently management allocates capital to generate profits. Companies compounding capital at ROIC > 15% possess durable competitive moats.",
      variables: [
        { name: "NOPAT", desc: "Net Operating Profit After Tax" },
        { name: "InvestedCapital", desc: "Net total debt + shareholders' equity minus excess cash" },
      ],
      insight: "Filters the tradable universe down to resilient high-quality compounders capable of surviving recessions.",
    },
    {
      id: "inverse_vol",
      layer: "Risk & Portfolio",
      name: "Inverse-Volatility Risk Allocation",
      math: "w_i = \\frac{1 / \\sigma_i}{\\sum_{j=1}^N (1 / \\sigma_j)}, \\quad DollarAllocation_i = Capital \\times w_i",
      plainFormula: "Weight_i = (1 / Volatility_i) / Sum(1 / Volatility_all)",
      description:
        "Allocates capital inversely proportional to realized 20-day volatility so that each holding contributes equal risk to the aggregate portfolio.",
      variables: [
        { name: "\\sigma_i", desc: "20-day annualized realized return volatility of asset i" },
        { name: "Capital", desc: "Total cash allocated to the strategy bucket" },
      ],
      insight: "Ensures volatile tech positions cannot dominate portfolio variance over stable dividend or healthcare positions.",
    },
    {
      id: "macro_regimes",
      layer: "L2 Macro Intelligence",
      name: "4-Quadrant Macro Regime Detector",
      math: "\\text{Trend} = Close_{SPY} > SMA_{200}(SPY), \\quad \\text{Vol} = \\sigma_{20}(SPY) > Median(\\sigma_{504})",
      plainFormula: "Trend = (SPY > 200 SMA), Volatility = (20-day Vol > 2-Year Median Vol)",
      description:
        "Dynamically classifies macroeconomic conditions into 4 quadrants to modulate overall portfolio risk exposure and defensive cash allocations.",
      variables: [
        { name: "BULL_LOW_VOL", desc: "SPY > 200 SMA, Low Vol -> 100% target equity exposure, aggressive momentum" },
        { name: "BULL_HIGH_VOL", desc: "SPY > 200 SMA, High Vol -> 70% target equity exposure, tighter ATR trailing stops" },
        { name: "BEAR_LOW_VOL", desc: "SPY < 200 SMA, Low Vol -> 30% target equity exposure, selective high-ROIC value" },
        { name: "BEAR_HIGH_VOL", desc: "SPY < 200 SMA, High Vol -> 0% target exposure, 100% Cash / Defensive hedge" },
      ],
      insight: "Saves the portfolio from devastating 40-50% drawdowns during major historical bear markets (2008, 2020, 2022).",
    },
    {
      id: "executive_catalyst",
      layer: "L4 AI & Executive NLP",
      name: "CEO Catalyst & Product Breakthrough Scoring",
      math: "Score_{catalyst} = \\sum_{k=1}^K w_k \\times \\text{Sentiment}_k \\times \\mathbb{I}_{\\text{CEO/Product}}(k)",
      plainFormula: "Catalyst Score = Weighted Sum of (Sentiment * Executive/Breakthrough Indicator)",
      description:
        "Real-time LLM scoring of statements by key executives (Elon Musk, Jensen Huang, Satya Nadella) and breakthrough product cycle releases (AI hardware, major contract wins, FDA approvals).",
      variables: [
        { name: "Sentiment_k", desc: "Structured LLM sentiment score from -1.0 to +1.0" },
        { name: "w_k", desc: "Exponential half-life time decay based on publication timestamp" },
        { name: "\\mathbb{I}_{\\text{CEO/Product}}", desc: "Binary indicator identifying executive/catalyst relevance" },
      ],
      insight: "Captures transformative corporate inflection points days before traditional quarterly earnings reflect the revenue surge.",
    },
    {
      id: "geopolitical_shock",
      layer: "L4 AI & Macro Defense",
      name: "Geopolitical & Tariff Shock Decay Filter",
      math: "\\text{ShockExposure} = \\max\\left(0, 1.0 - \\gamma \\times |\\text{NegativeMacroScore}|\\right)",
      plainFormula: "Exposure = Max(0, 1.0 - Sensitivity * Negative Policy News)",
      description:
        "Monitors breaking macroeconomic policy shocks (tariff announcements, presidential executive orders, trade sanctions) to reduce beta exposure on vulnerable export/import sectors.",
      variables: [
        { name: "\\gamma", desc: "Sector tariff sensitivity multiplier (1.2x for semiconductors/automotive)" },
        { name: "NegativeMacroScore", desc: "LLM severity assessment of policy trade disruption" },
      ],
      insight: "Protects high-growth momentum portfolios from sudden geopolitical flash crashes.",
    },
    {
      id: "market_impact_slippage",
      layer: "Execution & Cost Model",
      name: "Square-Root Law Market Impact Slippage",
      math: "\\text{Slippage\\%} = k \\times \\sigma_{\\text{daily}} \\times \\sqrt{\\frac{\\text{OrderNotional}}{\\text{ADV}_{20}}}",
      plainFormula: "Slippage % = k * Daily_Volatility * Sqrt(Order_Dollar_Value / 20-Day_Average_Volume)",
      description:
        "Almgren & Chriss institutional market impact law. Penalizes large orders executed in thin liquidity, guaranteeing that backtests reflect true execution drag.",
      variables: [
        { name: "k", desc: "Slippage severity coefficient (k = 1.0 default, k = 2.0 under Gate 4 stress testing)" },
        { name: "\\sigma_{\\text{daily}}", desc: "Daily asset volatility (~2% annualized)" },
        { name: "\\text{ADV}_{20}", desc: "20-day Average Daily Dollar Volume" },
      ],
      insight: "Keeps the strategy honest by preventing backtests from profiting off illiquid micro-caps that cannot be traded at scale in reality.",
    },
  ];

  const phases = [
    {
      phase: "Phase 1",
      title: "Universe Screening & Liquidity Filtering",
      cadence: "Quarterly / Semi-Annual",
      icon: ShieldCheck,
      color: "border-accent text-accent",
      bullets: [
        "Screen 1,000+ US equities for 20-day ADV >= $20,000,000 to eliminate slippage & market impact.",
        "Filter minimum share price >= $5.00 to exclude penny stocks and illiquid OTC names.",
        "Validate point-in-time index membership and fundamental quality (ROIC > 8%, Piotroski >= 6).",
        "Result: High-liquidity, institutional-grade tradable candidate pool of ~60-100 stocks.",
      ],
    },
    {
      phase: "Phase 2",
      title: "Factor Ranking & Machine Learning Scoring",
      cadence: "Monthly Rebalance",
      icon: Sparkles,
      color: "border-pos text-pos",
      bullets: [
        "Compute 12-1M Momentum ROC, Valuation Z-scores, and Sloan Accruals for all pool candidates.",
        "Run trained LightGBM gradient-boosted trees to predict forward return distribution with SHAP attributions.",
        "Integrate L4 real-time LLM financial news sentiment and narrative momentum scores.",
        "Rank order candidate pool and select Top N (Top 5 to 10) high-conviction opportunities.",
      ],
    },
    {
      phase: "Phase 3",
      title: "Macro Regime Conditioning & Risk Defense",
      cadence: "Daily Pre-Market",
      icon: Activity,
      color: "border-warning text-warning",
      bullets: [
        "Evaluate SPY 200 SMA trend condition and 20-day realized volatility vs 2-year median.",
        "If BEAR_HIGH_VOL (Crisis Panic): scale equity target to 0% and hold 100% Cash.",
        "If BULL_LOW_VOL (Trending Momentum): allocate 100% target capital across selected positions.",
        "If BULL_HIGH_VOL (Choppy Market): scale exposure to 70% and tighten stop bands.",
      ],
    },
    {
      phase: "Phase 4",
      title: "Inverse-Vol Risk Sizing & Order Routing",
      cadence: "t+1 Market-on-Open",
      icon: Calculator,
      color: "border-pos text-pos",
      bullets: [
        "Size candidate positions using Inverse-Volatility weighting (w_i proportional to 1/vol_i).",
        "Verify all orders against Centralized Risk Limits (§6.2 HardLimitsValidator).",
        "Submit Market-on-Open (MOO) or Limit orders via OMS with strict slippage and fee accounting.",
        "Strict t+1 fill timing rule: decision on bar t close executes on bar t+1 open (zero lookahead).",
      ],
    },
    {
      phase: "Phase 5",
      title: "Dynamic Position & Trailing Stop Management",
      cadence: "Intraday & Daily Close",
      icon: TrendingUp,
      color: "border-accent text-accent",
      bullets: [
        "Continuously recalculate 3.0x ATR trailing stop losses based on peak execution prices.",
        "Enforce mandatory Earnings Blackout Guard (no high-beta entries 2 days pre-earnings).",
        "Autonomous Emergency Kill-Switch monitoring (halts and liquidates on unexpected drawdowns).",
        "Sacred trade records written to append-only database with cryptographic audit trail.",
      ],
    },
  ];

  return (
    <div className="card-panel space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-border pb-4">
        <div className="flex items-center gap-2.5">
          <Layers className="w-5 h-5 text-pos" />
          <div>
            <h3 className="text-sm font-bold font-mono text-text-1">
              Strategy Blueprint & Quantitative Alpha Stack
            </h3>
            <p className="text-xs font-mono text-text-3">
              100% inspectable mathematical models, indicator formulas & execution subsystems
              {strategyVersionId ? ` · ${strategyVersionId}` : ""}
            </p>
          </div>
        </div>

        {/* Tab Selector */}
        <div className="flex items-center gap-1 bg-surface-2 p-1 rounded border border-border">
          <button
            onClick={() => setActiveTab("stack")}
            className={`px-3 py-1 text-xs font-mono rounded transition-all ${
              activeTab === "stack"
                ? "bg-surface-3 text-pos font-semibold border border-border"
                : "text-text-3 hover:text-text-1"
            }`}
          >
            Alpha Stack (L1-L4)
          </button>
          <button
            onClick={() => setActiveTab("formulas")}
            className={`px-3 py-1 text-xs font-mono rounded transition-all ${
              activeTab === "formulas"
                ? "bg-surface-3 text-pos font-semibold border border-border"
                : "text-text-3 hover:text-text-1"
            }`}
          >
            Formulas & Math
          </button>
          <button
            onClick={() => setActiveTab("phases")}
            className={`px-3 py-1 text-xs font-mono rounded transition-all ${
              activeTab === "phases"
                ? "bg-surface-3 text-pos font-semibold border border-border"
                : "text-text-3 hover:text-text-1"
            }`}
          >
            Multi-Phase Pipeline
          </button>
          <button
            onClick={() => setActiveTab("models")}
            className={`px-3 py-1 text-xs font-mono rounded transition-all ${
              activeTab === "models"
                ? "bg-surface-3 text-pos font-semibold border border-border"
                : "text-text-3 hover:text-text-1"
            }`}
          >
            AI/ML & SHAP
          </button>
        </div>
      </div>

      {/* TAB 1: 4-LAYER ALPHA STACK */}
      {activeTab === "stack" && (
        <div className="space-y-4">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {/* L4 Narrative */}
            <div className="p-4 rounded border border-border bg-surface-2 space-y-2">
              <div className="flex items-center justify-between">
                <span className="terminal-badge bg-accent/15 text-accent border border-accent/30 font-semibold">
                  Layer 4: Narrative & LLM Intelligence
                </span>
                <span className="text-[11px] font-mono text-text-3">Real-Time News Stream</span>
              </div>
              <p className="text-xs text-text-2 font-mono leading-relaxed">
                Ingests live financial news via Alpaca WebSocket and SEC filings. Evaluates breaking catalysts using structured JSON contracts:
              </p>
              <div className="bg-surface-1 p-2.5 rounded border border-border text-[11px] font-mono text-text-2 space-y-1">
                <div>• <span className="text-text-1 font-semibold">Sentiment Score:</span> Normalized -1.0 (fraud/litigation) to +1.0 (breakthrough).</div>
                <div>• <span className="text-text-1 font-semibold">Impact Horizon:</span> SHORT (1-3d), MEDIUM (1-4w), LONG (1-12m).</div>
                <div>• <span className="text-text-1 font-semibold">LLM Rationale:</span> Concise plain-English explanation generated per article.</div>
              </div>
            </div>

            {/* L3 Fundamentals */}
            <div className="p-4 rounded border border-border bg-surface-2 space-y-2">
              <div className="flex items-center justify-between">
                <span className="terminal-badge bg-pos/15 text-pos border border-pos/30 font-semibold">
                  Layer 3: Fundamental GARP & Quality
                </span>
                <span className="text-[11px] font-mono text-text-3">Point-in-Time Financials</span>
              </div>
              <p className="text-xs text-text-2 font-mono leading-relaxed">
                Screens audited balance sheets and income statements strictly anchored to SEC filing timestamps (zero lookahead):
              </p>
              <div className="bg-surface-1 p-2.5 rounded border border-border text-[11px] font-mono text-text-2 space-y-1">
                <div>• <span className="text-text-1 font-semibold">ROIC:</span> Operating Profit / Invested Capital (&gt; 8% minimum threshold).</div>
                <div>• <span className="text-text-1 font-semibold">Sloan Accrual Ratio:</span> Flags high-risk earnings inflated by accounting accruals.</div>
                <div>• <span className="text-text-1 font-semibold">Piotroski F-Score (0-9):</span> Tests financial health and profitability momentum.</div>
              </div>
            </div>

            {/* L2 Statistical & ML */}
            <div className="p-4 rounded border border-border bg-surface-2 space-y-2">
              <div className="flex items-center justify-between">
                <span className="terminal-badge bg-warning/15 text-warning border border-warning/30 font-semibold">
                  Layer 2: Statistical & Machine Learning
                </span>
                <span className="text-[11px] font-mono text-text-3">Non-Linear Prediction</span>
              </div>
              <p className="text-xs text-text-2 font-mono leading-relaxed">
                Processes 20 technical and statistical features through Gradient Boosted Decision Trees (LightGBM) with Purged K-Fold validation:
              </p>
              <div className="bg-surface-1 p-2.5 rounded border border-border text-[11px] font-mono text-text-2 space-y-1">
                <div>• <span className="text-text-1 font-semibold">12-1 Month Momentum:</span> Relative strength ranking across large-cap universe.</div>
                <div>• <span className="text-text-1 font-semibold">SHAP Feature Attribution:</span> Local explanation of exact driver weights per trade.</div>
                <div>• <span className="text-text-1 font-semibold">4-Quadrant Macro Regime:</span> Dynamic position scaling based on SPY trend & vol.</div>
              </div>
            </div>

            {/* L1 Technical */}
            <div className="p-4 rounded border border-border bg-surface-2 space-y-2">
              <div className="flex items-center justify-between">
                <span className="terminal-badge bg-text-1/15 text-text-1 border border-text-1/30 font-semibold">
                  Layer 1: Technical & Trend Following
                </span>
                <span className="text-[11px] font-mono text-text-3">Execution & Risk Trailing</span>
              </div>
              <p className="text-xs text-text-2 font-mono leading-relaxed">
                Deterministic price action filters and trailing stop loss models executing strictly at t+1 Market-on-Open:
              </p>
              <div className="bg-surface-1 p-2.5 rounded border border-border text-[11px] font-mono text-text-2 space-y-1">
                <div>• <span className="text-text-1 font-semibold">200/50 SMA Trend Filter:</span> Only long positions in confirmed macro uptrends.</div>
                <div>• <span className="text-text-1 font-semibold">RSI Pullbacks:</span> Oversold entry triggers (RSI 14 &lt; 40 or RSI 2 &lt; 10).</div>
                <div>• <span className="text-text-1 font-semibold">3x ATR Trailing Stops:</span> Volatility-adjusted trailing profit locks.</div>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* TAB 2: MATHEMATICAL FORMULAS */}
      {activeTab === "formulas" && (
        <div className="space-y-3">
          {formulas.map((f) => {
            const isExpanded = expandedFormula === f.id;
            return (
              <div
                key={f.id}
                className="border border-border rounded bg-surface-2 overflow-hidden transition-all"
              >
                <button
                  onClick={() => setExpandedFormula(isExpanded ? null : f.id)}
                  className="w-full p-3.5 flex items-center justify-between text-left hover:bg-surface-3 transition-colors"
                >
                  <div className="flex items-center gap-3">
                    <span className="terminal-badge bg-surface-1 border border-border text-pos font-semibold text-[10px]">
                      {f.layer}
                    </span>
                    <span className="text-xs font-bold font-mono text-text-1">{f.name}</span>
                  </div>
                  <div className="flex items-center gap-2 text-text-3">
                    <span className="text-[11px] font-mono hidden sm:inline">{f.plainFormula}</span>
                    {isExpanded ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
                  </div>
                </button>

                {isExpanded && (
                  <div className="p-4 border-t border-border bg-surface-1 space-y-3">
                    <div className="p-3 bg-surface-2 rounded border border-border font-mono text-xs text-pos font-semibold text-center">
                      <code>{f.plainFormula}</code>
                    </div>

                    <p className="text-xs text-text-2 font-mono leading-relaxed">{f.description}</p>

                    <div className="space-y-1.5">
                      <div className="text-[11px] font-mono font-semibold text-text-1 uppercase">Parameters & Variables:</div>
                      <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                        {f.variables.map((v, i) => (
                          <div key={i} className="p-2 bg-surface-2 rounded border border-border text-[11px] font-mono">
                            <span className="text-accent font-semibold">{v.name}:</span>{" "}
                            <span className="text-text-2">{v.desc}</span>
                          </div>
                        ))}
                      </div>
                    </div>

                    <div className="p-2.5 bg-pos/10 border border-pos/30 rounded text-xs font-mono text-pos flex items-start gap-2">
                      <CheckCircle2 className="w-4 h-4 shrink-0 mt-0.5" />
                      <div>
                        <span className="font-semibold">Institutional Quantitative Rationale:</span> {f.insight}
                      </div>
                    </div>
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}

      {/* TAB 3: MULTI-PHASE EXECUTION PIPELINE */}
      {activeTab === "phases" && (
        <div className="space-y-4">
          <p className="text-xs font-mono text-text-2">
            Every strategy executes through 5 strictly segregated lifecycle phases, ensuring zero lookahead bias and centralized risk management:
          </p>

          <div className="grid grid-cols-1 gap-3">
            {phases.map((p, idx) => {
              const Icon = p.icon;
              return (
                <div key={idx} className="p-4 rounded border border-border bg-surface-2 flex flex-col md:flex-row md:items-center justify-between gap-4">
                  <div className="flex items-start gap-3">
                    <div className={`p-2 rounded border bg-surface-1 ${p.color}`}>
                      <Icon className="w-4 h-4" />
                    </div>
                    <div className="space-y-1">
                      <div className="flex items-center gap-2">
                        <span className="text-[10px] font-mono font-bold uppercase tracking-wider text-text-3">
                          {p.phase} · {p.cadence}
                        </span>
                      </div>
                      <h4 className="text-xs font-bold font-mono text-text-1">{p.title}</h4>
                      <ul className="text-xs text-text-2 font-mono space-y-1 pt-1">
                        {p.bullets.map((b, i) => (
                          <li key={i} className="flex items-start gap-1.5">
                            <span className="text-pos font-bold">›</span>
                            <span>{b}</span>
                          </li>
                        ))}
                      </ul>
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* TAB 4: AI/ML & SHAP EXPLAINABILITY */}
      {activeTab === "models" && (
        <div className="space-y-4">
          <div className="p-4 rounded border border-border bg-surface-2 space-y-3">
            <div className="flex items-center justify-between">
              <span className="terminal-badge bg-pos/15 text-pos border border-pos/30 font-semibold">
                LightGBM Gradient Boosted Decision Trees
              </span>
              <span className="text-xs font-mono text-text-3">Purged K-Fold CV (5 Folds)</span>
            </div>
            <p className="text-xs text-text-2 font-mono leading-relaxed">
              Models are retrained periodically with Purged K-Fold Cross Validation and 5-day embargo quarantine windows (Lopez de Prado method) to strictly eliminate serial correlation and information leakage.
            </p>

            <div className="border border-border rounded bg-surface-1 p-3 space-y-2">
              <div className="text-xs font-mono font-semibold text-text-1">
                Sample Local SHAP (Shapley Additive exPlanations) Attribution:
              </div>
              <p className="text-[11px] font-mono text-text-3">
                For every stock signal, ATLAS decomposes the non-linear prediction into exact additive factor contributions:
              </p>

              <div className="space-y-2 pt-2">
                {[
                  { factor: "RSI(14) Oversold Pullback", shap: "+0.18", impact: "pos", width: "75%" },
                  { factor: "12-1 Month Momentum Decile", shap: "+0.14", impact: "pos", width: "60%" },
                  { factor: "Point-in-Time ROIC (> 25%)", shap: "+0.09", impact: "pos", width: "40%" },
                  { factor: "Low Sloan Accrual Ratio (< 0.02)", shap: "+0.06", impact: "pos", width: "25%" },
                  { factor: "20-Day Realized Volatility Spike", shap: "-0.11", impact: "neg", width: "45%" },
                  { factor: "Earnings Event Blackout (< 48h)", shap: "-0.08", impact: "neg", width: "35%" },
                ].map((item, i) => (
                  <div key={i} className="flex items-center justify-between text-xs font-mono gap-3">
                    <span className="w-56 text-text-2 truncate">{item.factor}</span>
                    <div className="flex-1 h-2.5 bg-surface-3 rounded overflow-hidden relative">
                      <div
                        className={`h-full rounded ${item.impact === "pos" ? "bg-pos" : "bg-neg"}`}
                        style={{ width: item.width }}
                      />
                    </div>
                    <span
                      className={`w-12 text-right font-semibold ${
                        item.impact === "pos" ? "text-pos" : "text-neg"
                      }`}
                    >
                      {item.shap}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
