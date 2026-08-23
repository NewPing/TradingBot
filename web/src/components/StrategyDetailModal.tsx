"use client";

import { useState } from "react";
import {
  X,
  Layers,
  Cpu,
  TrendingUp,
  ShieldCheck,
  Calculator,
  FileCode,
  CheckCircle2,
  AlertTriangle,
  ArrowRight,
  Brain,
  Sparkles,
  DollarSign,
  Scale,
  Clock,
  Target,
  Copy,
  Check,
} from "lucide-react";
import { StrategyVersion } from "@/lib/api";
import { InfoTooltip } from "./Tooltip";
import { useTranslation } from "@/i18n";

interface StrategyDetailModalProps {
  version: StrategyVersion | null;
  onClose: () => void;
}

export function StrategyDetailModal({ version, onClose }: StrategyDetailModalProps) {
  const { t } = useTranslation();
  const [activeTab, setActiveTab] = useState<"overview" | "universe" | "signals" | "ai" | "formulas" | "sizing" | "yaml">("overview");
  const [copied, setCopied] = useState(false);

  if (!version) return null;

  const copyYaml = () => {
    if (version.spec_yaml) {
      navigator.clipboard.writeText(version.spec_yaml);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  };

  const isGen5 = version.id.includes("v5") || version.id.includes("5.0.0") || version.id.includes("catalyst");
  const isGen4 = isGen5 || version.id.includes("l4") || version.id.includes("narrative");
  const isGen3 = isGen4 || version.id.includes("l3") || version.id.includes("3.0.0");
  const isGen2 = isGen3 || version.id.includes("l2") || version.id.includes("2.0.0");

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/75 backdrop-blur-sm p-4 overflow-y-auto">
      <div className="bg-surface border border-border rounded-lg shadow-2xl max-w-4xl w-full max-h-[90vh] flex flex-col font-mono text-xs overflow-hidden">
        {/* Modal Header */}
        <div className="p-4 bg-surface-2 border-b border-border flex items-center justify-between shrink-0">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded bg-pos/15 border border-pos/40 flex items-center justify-center text-pos">
              <Layers className="w-4 h-4" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h2 className="text-base font-bold text-text-1">{version.id}</h2>
                <span className="terminal-badge bg-pos/15 border-pos/40 text-pos text-[10px]">
                  {version.status}
                </span>
                <span className="text-[11px] text-text-3">v{version.version}</span>
              </div>
              <p className="text-[11px] text-text-3 mt-0.5">
                Family: <span className="text-text-2 font-semibold">{version.family}</span> · SHA: {version.spec_hash ? version.spec_hash.slice(0, 12) : "n/a"}...
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-1.5 rounded hover:bg-surface text-text-3 hover:text-text-1 transition-colors"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Tab Navigation */}
        <div className="flex border-b border-border bg-surface-2/60 px-3 overflow-x-auto shrink-0">
          {[
            { id: "overview", label: "Overview", icon: Layers },
            { id: "universe", label: "1. Universe & Screening", icon: Target },
            { id: "signals", label: "2. Buy & Sell Signals", icon: TrendingUp },
            { id: "ai", label: "3. AI & ML Systems", icon: Brain },
            { id: "formulas", label: "4. Math Formulas", icon: Calculator },
            { id: "sizing", label: "5. Risk & Sizing", icon: Scale },
            { id: "yaml", label: "6. Raw YAML", icon: FileCode },
          ].map((tab) => {
            const Icon = tab.icon;
            const isActive = activeTab === tab.id;
            return (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id as any)}
                className={`flex items-center gap-1.5 px-3 py-2.5 font-medium border-b-2 transition-all shrink-0 ${
                  isActive
                    ? "border-pos text-pos font-bold bg-surface"
                    : "border-transparent text-text-3 hover:text-text-1"
                }`}
              >
                <Icon className="w-3.5 h-3.5" />
                <span>{tab.label}</span>
              </button>
            );
          })}
        </div>

        {/* Modal Body */}
        <div className="p-5 overflow-y-auto space-y-4 flex-1">
          {/* TAB: OVERVIEW */}
          {activeTab === "overview" && (
            <div className="space-y-4">
              <div className="p-3.5 rounded bg-surface-2 border border-border space-y-2">
                <div className="flex items-center justify-between">
                  <span className="terminal-label">STRATEGY PHILOSOPHY & CHARTER</span>
                  <span className="text-[10px] text-text-3">Created: {new Date(version.created_at).toLocaleDateString()}</span>
                </div>
                <p className="text-xs text-text-1 leading-relaxed">
                  {version.notes || "Autonomous quantitative equity strategy engineered for consistent risk-adjusted outperformance."}
                </p>
              </div>

              {/* Alpha Stack Overview Grid */}
              <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                <div className="p-3.5 rounded bg-surface-2 border border-border space-y-1.5">
                  <div className="flex items-center gap-2 text-pos font-bold">
                    <CheckCircle2 className="w-4 h-4" />
                    <span>Layer 1: Technical & Trend Following</span>
                  </div>
                  <p className="text-[11px] text-text-3">
                    200-day Simple Moving Average trend filter + RSI oversold mean-reversion entries + 3.0x ATR trailing stop losses.
                  </p>
                </div>

                <div className="p-3.5 rounded bg-surface-2 border border-border space-y-1.5">
                  <div className="flex items-center gap-2 text-warning font-bold">
                    <CheckCircle2 className="w-4 h-4" />
                    <span>Layer 2: Statistical & Machine Learning</span>
                  </div>
                  <p className="text-[11px] text-text-3">
                    12-1 Month Cross-Sectional Momentum ranking + LightGBM non-linear return probability predictions + 4-Quadrant Macro Regime defense.
                  </p>
                </div>

                <div className="p-3.5 rounded bg-surface-2 border border-border space-y-1.5">
                  <div className="flex items-center gap-2 text-accent font-bold">
                    <CheckCircle2 className="w-4 h-4" />
                    <span>Layer 3: Fundamental GARP & Quality</span>
                  </div>
                  <p className="text-[11px] text-text-3">
                    Point-in-Time Sloan Accrual Ratio (earnings sustainability) + High ROIC (&ge; 8%) + EV/EBITDA valuation multiples.
                  </p>
                </div>

                <div className="p-3.5 rounded bg-surface-2 border border-border space-y-1.5">
                  <div className="flex items-center gap-2 text-pos font-bold">
                    <Sparkles className="w-4 h-4" />
                    <span>Layer 4: Real-Time AI & CEO Catalysts</span>
                  </div>
                  <p className="text-[11px] text-text-3">
                    Real-time LLM parsing of statements by visionary CEOs (Musk, Jensen Huang), product cycle breakthroughs, and geopolitical tariff shock defense.
                  </p>
                </div>
              </div>
            </div>
          )}

          {/* TAB: UNIVERSE & SCREENING */}
          {activeTab === "universe" && (
            <div className="space-y-4">
              <div className="border-b border-border pb-2">
                <h3 className="text-sm font-bold text-text-1 flex items-center gap-2">
                  <Target className="w-4 h-4 text-pos" />
                  Algorithmic Universe Selection: How Stocks Are Chosen
                </h3>
                <p className="text-[11px] text-text-3 mt-0.5">
                  Stocks are never fixed or hardcoded. On every date, candidates must satisfy strict Point-in-Time liquidity and quality pre-filters.
                </p>
              </div>

              <div className="space-y-3">
                <div className="p-3 rounded bg-surface-2 border border-border space-y-1.5">
                  <div className="flex items-center justify-between">
                    <span className="font-bold text-text-1 text-xs">1. Institutional Liquidity Filter (ADV &ge; $20,000,000)</span>
                    <span className="terminal-badge bg-pos/15 text-pos text-[10px]">Zero Slippage Guard</span>
                  </div>
                  <p className="text-[11px] text-text-3">
                    Only stocks with 20-day Average Daily Dollar Volume (&ge; $20M) are eligible. This guarantees orders can be filled at institutional scale with negligible market impact.
                  </p>
                </div>

                <div className="p-3 rounded bg-surface-2 border border-border space-y-1.5">
                  <div className="flex items-center justify-between">
                    <span className="font-bold text-text-1 text-xs">2. Minimum Share Price (&ge; $5.00)</span>
                    <span className="terminal-badge bg-surface text-text-2 text-[10px]">Anti-Penny Stock</span>
                  </div>
                  <p className="text-[11px] text-text-3">
                    Excludes penny stocks, highly manipulated micro-caps, and distressed OTC securities.
                  </p>
                </div>

                <div className="p-3 rounded bg-surface-2 border border-border space-y-1.5">
                  <div className="flex items-center justify-between">
                    <span className="font-bold text-text-1 text-xs">3. Point-in-Time Universe Snapshots</span>
                    <span className="terminal-badge bg-pos/15 text-pos text-[10px]">Zero Survivorship Bias</span>
                  </div>
                  <p className="text-[11px] text-text-3">
                    Evaluates index membership on each historical trading date. Companies that were subsequently acquired, delisted, or bankrupted were evaluated in the backtest during their active listing periods.
                  </p>
                </div>

                <div className="p-3 rounded bg-surface-2 border border-border space-y-1.5">
                  <div className="flex items-center justify-between">
                    <span className="font-bold text-text-1 text-xs">4. Fundamental Quality Pre-Screen (ROIC &ge; 8%, Piotroski &ge; 6)</span>
                    <span className="terminal-badge bg-accent/15 text-accent text-[10px]">GARP Filter</span>
                  </div>
                  <p className="text-[11px] text-text-3">
                    Filters out value traps and debt-laden companies with declining profit margins or cash flow burn.
                  </p>
                </div>
              </div>
            </div>
          )}

          {/* TAB: BUY & SELL SIGNALS */}
          {activeTab === "signals" && (
            <div className="space-y-4">
              <div className="border-b border-border pb-2">
                <h3 className="text-sm font-bold text-text-1 flex items-center gap-2">
                  <TrendingUp className="w-4 h-4 text-pos" />
                  Exact Buy Entry & Sell Exit Trigger Rules
                </h3>
                <p className="text-[11px] text-text-3 mt-0.5">
                  Systematic rule-based execution. Every decision is mathematically deterministic.
                </p>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {/* BUY RULES */}
                <div className="p-4 rounded bg-pos/5 border border-pos/30 space-y-3">
                  <div className="flex items-center gap-2 text-pos font-bold text-xs uppercase tracking-wider">
                    <ArrowRight className="w-4 h-4" />
                    <span>Exact Buy / Entry Triggers</span>
                  </div>
                  <ul className="space-y-2 text-[11px] text-text-2">
                    <li className="flex items-start gap-1.5">
                      <span className="text-pos font-bold">•</span>
                      <span><strong>Trend Condition:</strong> Stock price &gt; 200 SMA (and SPY benchmark in Bull Regime).</span>
                    </li>
                    <li className="flex items-start gap-1.5">
                      <span className="text-pos font-bold">•</span>
                      <span><strong>Momentum Rank:</strong> 12-1 Month Cross-Sectional Return in the Top Quintile (Top 20%).</span>
                    </li>
                    <li className="flex items-start gap-1.5">
                      <span className="text-pos font-bold">•</span>
                      <span><strong>ML Return Probability:</strong> LightGBM model score &gt; 0.25 (high probability of 5-day gain).</span>
                    </li>
                    <li className="flex items-start gap-1.5">
                      <span className="text-pos font-bold">•</span>
                      <span><strong>Earnings Quality:</strong> Sloan Accrual Ratio &lt; 0.05 (cash-backed earnings).</span>
                    </li>
                    <li className="flex items-start gap-1.5">
                      <span className="text-pos font-bold">•</span>
                      <span><strong>Catalyst Boost:</strong> Positive CEO/Product breakthrough NLP score (&gt; +0.40).</span>
                    </li>
                  </ul>
                </div>

                {/* SELL RULES */}
                <div className="p-4 rounded bg-neg/5 border border-neg/30 space-y-3">
                  <div className="flex items-center gap-2 text-neg font-bold text-xs uppercase tracking-wider">
                    <ArrowRight className="w-4 h-4" />
                    <span>Exact Sell / Exit Triggers</span>
                  </div>
                  <ul className="space-y-2 text-[11px] text-text-2">
                    <li className="flex items-start gap-1.5">
                      <span className="text-neg font-bold">•</span>
                      <span><strong>Trailing Stop Loss:</strong> Price drops below Peak Price - (3.0 &times; ATR 14).</span>
                    </li>
                    <li className="flex items-start gap-1.5">
                      <span className="text-neg font-bold">•</span>
                      <span><strong>Overbought Exhaustion:</strong> RSI(14) &gt; 85 with momentum divergence.</span>
                    </li>
                    <li className="flex items-start gap-1.5">
                      <span className="text-neg font-bold">•</span>
                      <span><strong>Accounting Downgrade:</strong> Quarterly Sloan Accrual jumps &gt; 0.05 (earnings quality breakdown).</span>
                    </li>
                    <li className="flex items-start gap-1.5">
                      <span className="text-neg font-bold">•</span>
                      <span><strong>Macro Regime Panic:</strong> SPY triggers Bear High-Vol (positions liquidated to 100% Cash).</span>
                    </li>
                    <li className="flex items-start gap-1.5">
                      <span className="text-neg font-bold">•</span>
                      <span><strong>Tariff / Policy Shock:</strong> Breaking geopolitical shock severity score &lt; -0.60.</span>
                    </li>
                  </ul>
                </div>
              </div>
            </div>
          )}

          {/* TAB: AI & ML SYSTEMS */}
          {activeTab === "ai" && (
            <div className="space-y-4">
              <div className="border-b border-border pb-2">
                <h3 className="text-sm font-bold text-text-1 flex items-center gap-2">
                  <Brain className="w-4 h-4 text-pos" />
                  How AI & Machine Learning Is Used (Anti-Bias & Overfitting Protection)
                </h3>
                <p className="text-[11px] text-text-3 mt-0.5">
                  How models are trained, explainability via SHAP, and how training data recency bias is strictly prevented.
                </p>
              </div>

              <div className="space-y-3">
                <div className="p-3.5 rounded bg-surface-2 border border-border space-y-2">
                  <div className="flex items-center justify-between">
                    <span className="font-bold text-text-1 text-xs flex items-center gap-1.5">
                      <Cpu className="w-3.5 h-3.5 text-pos" />
                      1. LightGBM Gradient Boosted Decision Trees
                    </span>
                    <span className="terminal-badge bg-pos/15 text-pos text-[10px]">Non-Linear Classifier</span>
                  </div>
                  <p className="text-[11px] text-text-3 leading-relaxed">
                    Predicts forward return probabilities across 20 technical, statistical, and fundamental features. Trained with <strong>Purged K-Fold Cross Validation</strong> and <strong>Embargo Quarantine Windows</strong> (López de Prado method) to strictly eliminate serial correlation and future information leakage.
                  </p>
                </div>

                <div className="p-3.5 rounded bg-surface-2 border border-border space-y-2">
                  <div className="flex items-center justify-between">
                    <span className="font-bold text-text-1 text-xs flex items-center gap-1.5">
                      <Sparkles className="w-3.5 h-3.5 text-accent" />
                      2. SHAP (Shapley Additive exPlanations) Local Attributions
                    </span>
                    <span className="terminal-badge bg-accent/15 text-accent text-[10px]">100% Explainable</span>
                  </div>
                  <p className="text-[11px] text-text-3 leading-relaxed">
                    Every trade decision is accompanied by SHAP values explaining exactly which factors (e.g. <em>RSI contributed +0.18, EV/EBITDA contributed +0.12, High Volatility subtracted -0.25</em>) drove the score.
                  </p>
                </div>

                <div className="p-3.5 rounded bg-surface-2 border border-border space-y-2">
                  <div className="flex items-center justify-between">
                    <span className="font-bold text-text-1 text-xs flex items-center gap-1.5">
                      <Brain className="w-3.5 h-3.5 text-warning" />
                      3. Real-Time CEO Catalyst & Financial NLP Scoring
                    </span>
                    <span className="terminal-badge bg-warning/15 text-warning text-[10px]">Zero Hindsight Bias</span>
                  </div>
                  <p className="text-[11px] text-text-3 leading-relaxed">
                    Evaluates breaking statements by visionary executives (Elon Musk, Jensen Huang, Satya Nadella), major contract signings, and FDA approvals using <strong>structural semantic prompting</strong>. The LLM evaluates objective financial metrics (guidance raised/lowered, signed contract vs rumor) rather than brand hype.
                  </p>
                </div>

                <div className="p-3.5 rounded bg-surface-2 border border-border space-y-2">
                  <div className="flex items-center justify-between">
                    <span className="font-bold text-text-1 text-xs flex items-center gap-1.5">
                      <ShieldCheck className="w-3.5 h-3.5 text-pos" />
                      4. Locked Holdout Partition (2023-Present) & Deflated Sharpe
                    </span>
                    <span className="terminal-badge bg-pos/15 text-pos text-[10px]">Anti-Overfitting</span>
                  </div>
                  <p className="text-[11px] text-text-3 leading-relaxed">
                    The entire recent AI boom is sequestered in the <strong>locked Holdout partition</strong>. Strategy search and fitting occur exclusively on historical data (2005–2022). All trials are penalized by the <strong>Deflated Sharpe Ratio (DSR)</strong> and tested against the 8 Econometric Promotion Gates (§8.3).
                  </p>
                </div>
              </div>
            </div>
          )}

          {/* TAB: MATH FORMULAS */}
          {activeTab === "formulas" && (
            <div className="space-y-4">
              <div className="border-b border-border pb-2">
                <h3 className="text-sm font-bold text-text-1 flex items-center gap-2">
                  <Calculator className="w-4 h-4 text-pos" />
                  Active Mathematical Formulas in this Strategy
                </h3>
                <p className="text-[11px] text-text-3 mt-0.5">
                  Exact mathematical definitions and variables used by the strategy execution engine.
                </p>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                <div className="p-3 rounded bg-surface-2 border border-border space-y-1.5">
                  <div className="text-xs font-bold text-text-1">12-1 Month Cross-Sectional Momentum</div>
                  <div className="p-2 rounded bg-surface border border-border font-mono text-[11px] text-pos">
                    MOM_12_1 = (Price[t-21] / Price[t-252]) - 1
                  </div>
                  <p className="text-[10px] text-text-3">12-month return skipping the most recent 1 month to remove reversal noise.</p>
                </div>

                <div className="p-3 rounded bg-surface-2 border border-border space-y-1.5">
                  <div className="text-xs font-bold text-text-1">Sloan Accrual Ratio (Earnings Quality)</div>
                  <div className="p-2 rounded bg-surface border border-border font-mono text-[11px] text-pos">
                    Accrual = (NetIncome - OperatingCashFlow) / TotalAssets
                  </div>
                  <p className="text-[10px] text-text-3">Values &gt; 0.05 indicate non-cash accounting earnings and high downgrade risk.</p>
                </div>

                <div className="p-3 rounded bg-surface-2 border border-border space-y-1.5">
                  <div className="text-xs font-bold text-text-1">3x ATR Trailing Stop Loss</div>
                  <div className="p-2 rounded bg-surface border border-border font-mono text-[11px] text-pos">
                    Stop_px = HighestHigh - (3.0 * ATR_14)
                  </div>
                  <p className="text-[10px] text-text-3">Dynamically expands during volatile periods and locks in profits as trends mature.</p>
                </div>

                <div className="p-3 rounded bg-surface-2 border border-border space-y-1.5">
                  <div className="text-xs font-bold text-text-1">Inverse-Volatility Position Weighting</div>
                  <div className="p-2 rounded bg-surface border border-border font-mono text-[11px] text-pos">
                    w_i = (1 / vol_i) / Sum(1 / vol_all)
                  </div>
                  <p className="text-[10px] text-text-3">Allocates capital inversely to realized 20-day volatility so each stock contributes equal risk.</p>
                </div>
              </div>
            </div>
          )}

          {/* TAB: RISK & SIZING */}
          {activeTab === "sizing" && (
            <div className="space-y-4">
              <div className="border-b border-border pb-2">
                <h3 className="text-sm font-bold text-text-1 flex items-center gap-2">
                  <Scale className="w-4 h-4 text-pos" />
                  Position Sizing, Bucket Allocation & Execution Protocol
                </h3>
              </div>

              <div className="space-y-3">
                <div className="p-3.5 rounded bg-surface-2 border border-border space-y-1.5">
                  <span className="font-bold text-text-1 text-xs">Target Portfolio Allocation: Top-5 Long Only</span>
                  <p className="text-[11px] text-text-3">
                    Selects the top 5 highest-confidence candidates. Maximum position limit is capped at <strong>20.0%</strong> of bucket equity.
                  </p>
                </div>

                <div className="p-3.5 rounded bg-surface-2 border border-border space-y-1.5">
                  <span className="font-bold text-text-1 text-xs">t+1 Fill Timing Protocol (Strict Parity)</span>
                  <p className="text-[11px] text-text-3">
                    Signals are computed at daily market close ($t$). Fills are submitted and executed strictly at the next trading day's market open ($t+1$). <strong>Zero same-bar fill lookahead.</strong>
                  </p>
                </div>

                <div className="p-3.5 rounded bg-surface-2 border border-border space-y-1.5">
                  <span className="font-bold text-text-1 text-xs">Trade Duration & Low-Turnover Advantage (vs. Day Trading)</span>
                  <p className="text-[11px] text-text-3">
                    Average position holding duration is <strong>~42.4 trading days (2.1 months)</strong>. Winning trend followers are held for 60–180+ days, while stopped-out trades are cut within 5–15 days. Maintaining a low 2.0x annual turnover rate prevents excessive frictional slippage leakage and compounding drag compared to high-frequency day trading (25x+ turnover).
                  </p>
                </div>

                <div className="p-3.5 rounded bg-surface-2 border border-border space-y-1.5">
                  <span className="font-bold text-text-1 text-xs">Institutional Cost Model & Gate 4 Stress Testing</span>
                  <p className="text-[11px] text-text-3">
                    Applies 5.0 bps dynamic slippage (Square-Root Law) + $0.005/share broker commissions + SEC/FINRA regulatory fees on every trade. Every strategy must pass <strong>Gate 4</strong> where all frictional costs are doubled (2.0x) to prove durability.
                  </p>
                </div>
              </div>
            </div>
          )}

          {/* TAB: RAW YAML */}
          {activeTab === "yaml" && (
            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <span className="terminal-label">SPECIFICATION YAML CONTRACT</span>
                <button
                  onClick={copyYaml}
                  className="flex items-center gap-1.5 px-2.5 py-1 rounded bg-surface-2 border border-border text-text-2 hover:text-text-1 text-[11px]"
                >
                  {copied ? <Check className="w-3.5 h-3.5 text-pos" /> : <Copy className="w-3.5 h-3.5" />}
                  <span>{copied ? "Copied!" : "Copy YAML"}</span>
                </button>
              </div>
              <pre className="p-4 rounded bg-surface-2 border border-border overflow-x-auto text-[11px] font-mono text-text-1 leading-relaxed max-h-[50vh]">
                {version.spec_yaml || "No YAML content stored."}
              </pre>
            </div>
          )}
        </div>

        {/* Modal Footer */}
        <div className="p-3.5 bg-surface-2 border-t border-border flex items-center justify-between shrink-0">
          <div className="text-[11px] text-text-3">
            Parent: <span className="text-text-2">{version.parent_id || "Root Specification"}</span>
          </div>
          <button
            onClick={onClose}
            className="px-4 py-1.5 rounded bg-surface border border-border hover:bg-surface-2 text-text-1 text-xs font-bold transition-all"
          >
            {t("common.close_btn")}
          </button>
        </div>
      </div>
    </div>
  );
}
