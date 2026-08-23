"use client";

import { useState } from "react";
import Link from "next/link";
import {
  BookOpen,
  Terminal,
  Activity,
  Layers,
  Cpu,
  FileSpreadsheet,
  Newspaper,
  FlaskConical,
  Radio,
  ShieldCheck,
  ShieldAlert,
  Search,
  CheckCircle2,
  Lock,
  Zap,
  Scale,
  Sparkles,
  ArrowRight,
  TrendingUp,
  Clock,
} from "lucide-react";
import { useTranslation } from "@/i18n";
import { useWalkthrough } from "@/components/WalkthroughContext";

export default function DocsPage() {
  const { t } = useTranslation();
  const { openWalkthrough } = useWalkthrough();
  const [activeTab, setActiveTab] = useState<string>("workflow");
  const [searchQuery, setSearchQuery] = useState("");

  const tabs = [
    { id: "workflow", label: t("docs.tab_workflow"), icon: Terminal },
    { id: "alpha_stack", label: t("docs.tab_alpha_stack"), icon: Activity },
    { id: "versions", label: t("docs.tab_versions"), icon: Layers },
    { id: "regimes_ml", label: t("docs.tab_regimes_ml"), icon: Cpu },
    { id: "fundamentals", label: t("docs.tab_fundamentals"), icon: FileSpreadsheet },
    { id: "narrative", label: t("docs.tab_narrative"), icon: Newspaper },
    { id: "research", label: t("docs.tab_research"), icon: FlaskConical },
    { id: "execution_risk", label: t("docs.tab_execution_risk"), icon: Radio },
    { id: "glossary", label: t("docs.tab_glossary"), icon: BookOpen },
  ];

  return (
    <div className="space-y-6 pb-16 font-mono">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-border pb-5">
        <div>
          <div className="flex items-center gap-3">
            <h1 className="text-xl font-bold tracking-tight text-text-1 flex items-center gap-2">
              <BookOpen className="w-5 h-5 text-pos" />
              {t("docs.title")}
            </h1>
            <span className="text-[10px] px-2 py-0.5 rounded bg-pos/10 border border-pos/30 text-pos font-semibold">
              KNOWLEDGE BASE
            </span>
          </div>
          <p className="text-xs text-text-3 mt-1">
            {t("docs.subtitle")}
          </p>
        </div>

        <div className="flex items-center gap-2">
          <button
            onClick={() => openWalkthrough(0)}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded bg-pos text-bg text-xs font-bold hover:bg-pos/90 transition-all shadow-sm"
          >
            <Sparkles className="w-3.5 h-3.5" />
            <span>{t("docs.launch_walkthrough_btn")}</span>
          </button>
        </div>
      </div>

      {/* Tabs Navigation */}
      <div className="flex items-center gap-1.5 overflow-x-auto pb-2 border-b border-border text-xs">
        {tabs.map((tab) => {
          const Icon = tab.icon;
          const isActive = activeTab === tab.id;
          return (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={`flex items-center gap-2 px-3 py-2 rounded transition-all shrink-0 ${
                isActive
                  ? "bg-active text-pos border border-border border-b-2 border-b-pos font-semibold"
                  : "text-text-3 hover:text-text-1 hover:bg-surface border border-transparent"
              }`}
            >
              <Icon className={`w-3.5 h-3.5 ${isActive ? "text-pos" : "text-text-3"}`} />
              <span>{tab.label}</span>
            </button>
          );
        })}
      </div>

      {/* Tab 1: Workflow & User Process */}
      {activeTab === "workflow" && (
        <div className="space-y-6 animate-in fade-in duration-200">
          <div className="card-panel space-y-4">
            <div className="flex items-center gap-2 border-b border-border pb-3">
              <Terminal className="w-4 h-4 text-pos" />
              <h2 className="text-sm font-bold text-text-1">{t("docs.wf_title")}</h2>
            </div>
            <p className="text-xs text-text-2 leading-relaxed">
              {t("docs.wf_intro")}
            </p>

            <div className="grid grid-cols-1 md:grid-cols-4 gap-4 pt-2">
              <div className="p-4 bg-surface-2 border border-border rounded space-y-2">
                <div className="flex items-center justify-between">
                  <span className="text-xs font-bold text-pos">PHASE 1</span>
                  <Activity className="w-4 h-4 text-text-3" />
                </div>
                <h3 className="text-xs font-bold text-text-1">{t("docs.wf_step1_title")}</h3>
                <p className="text-[11px] text-text-3 leading-relaxed">
                  {t("docs.wf_step1_desc")}
                </p>
                <Link href="/models" className="text-[10px] text-pos hover:underline inline-block pt-1">
                  &rarr; {t("nav.models")}
                </Link>
              </div>

              <div className="p-4 bg-surface-2 border border-border rounded space-y-2">
                <div className="flex items-center justify-between">
                  <span className="text-xs font-bold text-info">PHASE 2</span>
                  <FileSpreadsheet className="w-4 h-4 text-text-3" />
                </div>
                <h3 className="text-xs font-bold text-text-1">{t("docs.wf_step2_title")}</h3>
                <p className="text-[11px] text-text-3 leading-relaxed">
                  {t("docs.wf_step2_desc")}
                </p>
                <Link href="/fundamentals" className="text-[10px] text-info hover:underline inline-block pt-1">
                  &rarr; {t("nav.fundamentals")}
                </Link>
              </div>

              <div className="p-4 bg-surface-2 border border-border rounded space-y-2">
                <div className="flex items-center justify-between">
                  <span className="text-xs font-bold text-warn">PHASE 3</span>
                  <FlaskConical className="w-4 h-4 text-text-3" />
                </div>
                <h3 className="text-xs font-bold text-text-1">{t("docs.wf_step3_title")}</h3>
                <p className="text-[11px] text-text-3 leading-relaxed">
                  {t("docs.wf_step3_desc")}
                </p>
                <Link href="/research" className="text-[10px] text-warn hover:underline inline-block pt-1">
                  &rarr; {t("nav.research")}
                </Link>
              </div>

              <div className="p-4 bg-surface-2 border border-border rounded space-y-2">
                <div className="flex items-center justify-between">
                  <span className="text-xs font-bold text-pos">PHASE 4</span>
                  <Radio className="w-4 h-4 text-text-3" />
                </div>
                <h3 className="text-xs font-bold text-text-1">{t("docs.wf_step4_title")}</h3>
                <p className="text-[11px] text-text-3 leading-relaxed">
                  {t("docs.wf_step4_desc")}
                </p>
                <Link href="/live" className="text-[10px] text-pos hover:underline inline-block pt-1">
                  &rarr; {t("nav.live")}
                </Link>
              </div>
            </div>
          </div>

          <div className="card-panel space-y-3">
            <div className="terminal-label">{t("docs.hard_invariants_title")}</div>
            <p className="text-xs text-text-2 leading-relaxed">
              {t("docs.hard_invariants_desc")}
            </p>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-3 text-xs pt-1">
              <div className="p-3 bg-surface-2 border border-border rounded space-y-1">
                <div className="font-bold text-pos">{t("tooltips.parity_title")}</div>
                <p className="text-[11px] text-text-3 leading-relaxed">
                  {t("tooltips.parity_desc")}
                </p>
              </div>
              <div className="p-3 bg-surface-2 border border-border rounded space-y-1">
                <div className="font-bold text-pos">{t("tooltips.lookahead_title")}</div>
                <p className="text-[11px] text-text-3 leading-relaxed">
                  {t("tooltips.lookahead_desc")}
                </p>
              </div>
              <div className="p-3 bg-surface-2 border border-border rounded space-y-1">
                <div className="font-bold text-warn">{t("tooltips.holdout_guard_title")}</div>
                <p className="text-[11px] text-text-3 leading-relaxed">
                  {t("tooltips.holdout_guard_desc")}
                </p>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Tab 2: The 4 Alpha Layers (L1-L4) */}
      {activeTab === "alpha_stack" && (
        <div className="space-y-6 animate-in fade-in duration-200">
          <div className="card-panel space-y-4">
            <div className="flex items-center gap-2 border-b border-border pb-3">
              <Activity className="w-4 h-4 text-pos" />
              <h2 className="text-sm font-bold text-text-1">{t("docs.alpha_stack_title")}</h2>
            </div>
            <p className="text-xs text-text-2 leading-relaxed">
              {t("docs.alpha_stack_intro")}
            </p>

            <div className="space-y-4 pt-2 text-xs">
              {/* L1 */}
              <div className="p-4 bg-surface-2 border border-border rounded space-y-2">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <span className="px-2 py-0.5 rounded bg-pos/10 border border-pos/30 text-pos font-bold text-[10px]">
                      LAYER 1
                    </span>
                    <span className="font-bold text-text-1">{t("docs.l1_full_title")}</span>
                  </div>
                  <Link href="/signals" className="text-pos hover:underline text-[11px]">
                    /signals &rarr;
                  </Link>
                </div>
                <p className="text-text-3 leading-relaxed text-[11px]">
                  {t("docs.l1_full_desc")}
                </p>
                <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 pt-1 text-[10px] text-text-2">
                  <div className="p-2 bg-surface rounded border border-border">• RSI (14) Momentum</div>
                  <div className="p-2 bg-surface rounded border border-border">• 200 SMA Trend Gating</div>
                  <div className="p-2 bg-surface rounded border border-border">• MACD Histogram</div>
                  <div className="p-2 bg-surface rounded border border-border">• 14-day ATR Volatility</div>
                </div>
              </div>

              {/* L2 */}
              <div className="p-4 bg-surface-2 border border-border rounded space-y-2">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <span className="px-2 py-0.5 rounded bg-info/10 border border-info/30 text-info font-bold text-[10px]">
                      LAYER 2
                    </span>
                    <span className="font-bold text-text-1">{t("docs.l2_full_title")}</span>
                  </div>
                  <Link href="/models" className="text-info hover:underline text-[11px]">
                    /models &rarr;
                  </Link>
                </div>
                <p className="text-text-3 leading-relaxed text-[11px]">
                  {t("docs.l2_full_desc")}
                </p>
                <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 pt-1 text-[10px] text-text-2">
                  <div className="p-2 bg-surface rounded border border-border">• LightGBM GBDT 5-day Dir</div>
                  <div className="p-2 bg-surface rounded border border-border">• 4-Quadrant Market Regime</div>
                  <div className="p-2 bg-surface rounded border border-border">• Purged K-Fold CV (Embargo)</div>
                  <div className="p-2 bg-surface rounded border border-border">• SHAP Feature Importance</div>
                </div>
              </div>

              {/* L3 */}
              <div className="p-4 bg-surface-2 border border-border rounded space-y-2">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <span className="px-2 py-0.5 rounded bg-warn/10 border border-warn/30 text-warn font-bold text-[10px]">
                      LAYER 3
                    </span>
                    <span className="font-bold text-text-1">{t("docs.l3_full_title")}</span>
                  </div>
                  <Link href="/fundamentals" className="text-warn hover:underline text-[11px]">
                    /fundamentals &rarr;
                  </Link>
                </div>
                <p className="text-text-3 leading-relaxed text-[11px]">
                  {t("docs.l3_full_desc")}
                </p>
                <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 pt-1 text-[10px] text-text-2">
                  <div className="p-2 bg-surface rounded border border-border">• Point-in-Time SEC Filings</div>
                  <div className="p-2 bg-surface rounded border border-border">• Sloan Accrual Quality</div>
                  <div className="p-2 bg-surface rounded border border-border">• ROIC & EV/EBITDA GARP</div>
                  <div className="p-2 bg-surface rounded border border-border">• Earnings Blackout Guard</div>
                </div>
              </div>

              {/* L4 */}
              <div className="p-4 bg-surface-2 border border-border rounded space-y-2">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <span className="px-2 py-0.5 rounded bg-purple-500/10 border border-purple-500/30 text-purple-400 font-bold text-[10px]">
                      LAYER 4
                    </span>
                    <span className="font-bold text-text-1">{t("docs.l4_full_title")}</span>
                  </div>
                  <Link href="/narrative" className="text-purple-400 hover:underline text-[11px]">
                    /narrative &rarr;
                  </Link>
                </div>
                <p className="text-text-3 leading-relaxed text-[11px]">
                  {t("docs.l4_full_desc")}
                </p>
                <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 pt-1 text-[10px] text-text-2">
                  <div className="p-2 bg-surface rounded border border-border">• Alpaca News Realtime Stream</div>
                  <div className="p-2 bg-surface rounded border border-border">• Versioned JSON LLM Prompts</div>
                  <div className="p-2 bg-surface rounded border border-border">• Decayed Narrative Momentum</div>
                  <div className="p-2 bg-surface rounded border border-border">• Short Borrow Cost Model</div>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Tab 3: Strategy Specs, Immutability & Lineage */}
      {activeTab === "versions" && (
        <div className="space-y-6 animate-in fade-in duration-200">
          <div className="card-panel space-y-4">
            <div className="flex items-center gap-2 border-b border-border pb-3">
              <Layers className="w-4 h-4 text-pos" />
              <h2 className="text-sm font-bold text-text-1">{t("docs.versions_title")}</h2>
            </div>
            <p className="text-xs text-text-2 leading-relaxed">
              {t("docs.versions_intro")}
            </p>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-xs pt-2">
              <div className="p-4 bg-surface-2 border border-border rounded space-y-2">
                <div className="text-pos font-bold flex items-center gap-1.5">
                  <Lock className="w-3.5 h-3.5" />
                  {t("docs.immutability_rule_title")}
                </div>
                <p className="text-[11px] text-text-3 leading-relaxed">
                  {t("docs.immutability_rule_desc")}
                </p>
              </div>

              <div className="p-4 bg-surface-2 border border-border rounded space-y-2">
                <div className="text-info font-bold flex items-center gap-1.5">
                  <Activity className="w-3.5 h-3.5" />
                  {t("docs.lineage_graph_title")}
                </div>
                <p className="text-[11px] text-text-3 leading-relaxed">
                  {t("docs.lineage_graph_desc")}
                </p>
              </div>
            </div>

            <div className="p-3 bg-active border border-border rounded flex items-center justify-between text-xs">
              <span className="text-text-2">{t("docs.versions_cta_text")}</span>
              <Link href="/versions" className="btn-primary py-1 px-3 text-xs">
                {t("nav.versions")} &rarr;
              </Link>
            </div>
          </div>
        </div>
      )}

      {/* Tab 4: Market Regimes & ML Explainability */}
      {activeTab === "regimes_ml" && (
        <div className="space-y-6 animate-in fade-in duration-200">
          <div className="card-panel space-y-4">
            <div className="flex items-center gap-2 border-b border-border pb-3">
              <Cpu className="w-4 h-4 text-pos" />
              <h2 className="text-sm font-bold text-text-1">{t("docs.regimes_title")}</h2>
            </div>
            <p className="text-xs text-text-2 leading-relaxed">
              {t("docs.regimes_intro")}
            </p>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 text-xs pt-2">
              <div className="p-3 bg-pos/10 border border-pos/30 rounded space-y-1">
                <div className="font-bold text-pos">{t("models.quadrant_bull_low_vol")}</div>
                <p className="text-[11px] text-text-2 leading-relaxed">
                  {t("docs.regime_bull_low_desc")}
                </p>
              </div>

              <div className="p-3 bg-warn/10 border border-warn/30 rounded space-y-1">
                <div className="font-bold text-warn">{t("models.quadrant_bull_high_vol")}</div>
                <p className="text-[11px] text-text-2 leading-relaxed">
                  {t("docs.regime_bull_high_desc")}
                </p>
              </div>

              <div className="p-3 bg-neg/10 border border-neg/30 rounded space-y-1">
                <div className="font-bold text-neg">{t("models.quadrant_bear_high_vol")}</div>
                <p className="text-[11px] text-text-2 leading-relaxed">
                  {t("docs.regime_bear_high_desc")}
                </p>
              </div>

              <div className="p-3 bg-warn/10 border border-warn/30 rounded space-y-1">
                <div className="font-bold text-warn">{t("models.quadrant_bear_low_vol")}</div>
                <p className="text-[11px] text-text-2 leading-relaxed">
                  {t("docs.regime_bear_low_desc")}
                </p>
              </div>
            </div>

            <div className="p-4 bg-surface-2 border border-border rounded space-y-2 text-xs">
              <div className="font-bold text-text-1">{t("docs.ml_cv_title")}</div>
              <p className="text-[11px] text-text-3 leading-relaxed">
                {t("docs.ml_cv_desc")}
              </p>
            </div>
          </div>
        </div>
      )}

      {/* Tab 5: Fundamentals & GARP Scorecards */}
      {activeTab === "fundamentals" && (
        <div className="space-y-6 animate-in fade-in duration-200">
          <div className="card-panel space-y-4">
            <div className="flex items-center gap-2 border-b border-border pb-3">
              <FileSpreadsheet className="w-4 h-4 text-pos" />
              <h2 className="text-sm font-bold text-text-1">{t("docs.fund_title")}</h2>
            </div>
            <p className="text-xs text-text-2 leading-relaxed">
              {t("docs.fund_intro")}
            </p>

            <div className="grid grid-cols-1 md:grid-cols-3 gap-4 text-xs pt-2">
              <div className="p-3.5 bg-surface-2 border border-border rounded space-y-1.5">
                <div className="font-bold text-pos">{t("tooltips.roic_title")}</div>
                <p className="text-[11px] text-text-3 leading-relaxed">
                  {t("tooltips.roic_desc")}
                </p>
              </div>

              <div className="p-3.5 bg-surface-2 border border-border rounded space-y-1.5">
                <div className="font-bold text-info">{t("tooltips.sloan_accrual_title")}</div>
                <p className="text-[11px] text-text-3 leading-relaxed">
                  {t("tooltips.sloan_accrual_desc")}
                </p>
              </div>

              <div className="p-3.5 bg-surface-2 border border-border rounded space-y-1.5">
                <div className="font-bold text-warn">{t("tooltips.blackout_guard_title")}</div>
                <p className="text-[11px] text-text-3 leading-relaxed">
                  {t("tooltips.blackout_guard_desc")}
                </p>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Tab 6: Narrative & LLM Scoring */}
      {activeTab === "narrative" && (
        <div className="space-y-6 animate-in fade-in duration-200">
          <div className="card-panel space-y-4">
            <div className="flex items-center gap-2 border-b border-border pb-3">
              <Newspaper className="w-4 h-4 text-pos" />
              <h2 className="text-sm font-bold text-text-1">{t("docs.narr_title")}</h2>
            </div>
            <p className="text-xs text-text-2 leading-relaxed">
              {t("docs.narr_intro")}
            </p>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-xs pt-2">
              <div className="p-4 bg-surface-2 border border-border rounded space-y-2">
                <div className="font-bold text-pos">{t("tooltips.narrative_momentum_title")}</div>
                <p className="text-[11px] text-text-3 leading-relaxed">
                  {t("tooltips.narrative_momentum_desc")}
                </p>
              </div>

              <div className="p-4 bg-surface-2 border border-border rounded space-y-2">
                <div className="font-bold text-info">{t("tooltips.short_selling_title")}</div>
                <p className="text-[11px] text-text-3 leading-relaxed">
                  {t("tooltips.short_selling_desc")}
                </p>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Tab 7: The Research Loop & 8 Promotion Gates */}
      {activeTab === "research" && (
        <div className="space-y-6 animate-in fade-in duration-200">
          <div className="card-panel space-y-4">
            <div className="flex items-center gap-2 border-b border-border pb-3">
              <FlaskConical className="w-4 h-4 text-pos" />
              <h2 className="text-sm font-bold text-text-1">{t("docs.research_title")}</h2>
            </div>
            <p className="text-xs text-text-2 leading-relaxed">
              {t("docs.research_intro")}
            </p>

            <div className="p-4 bg-surface-2 border border-border rounded space-y-3">
              <div className="text-xs font-bold text-pos flex items-center gap-2">
                <Scale className="w-4 h-4" />
                <span>{t("research.gatekeeper_8_rules_title")} (§8.3 Econometric Gatekeeper)</span>
              </div>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-3 text-[11px] text-text-3">
                <div className="p-2.5 bg-surface rounded border border-border">
                  <span className="font-bold text-text-1">Gate 1: {t("research.gate_1_title")}</span>
                  <p className="mt-0.5">{t("research.gate_1_desc")}</p>
                </div>
                <div className="p-2.5 bg-surface rounded border border-border">
                  <span className="font-bold text-text-1">Gate 2: {t("research.gate_2_title")}</span>
                  <p className="mt-0.5">{t("research.gate_2_desc")}</p>
                </div>
                <div className="p-2.5 bg-surface rounded border border-border">
                  <span className="font-bold text-text-1">Gate 3: {t("research.gate_3_title")}</span>
                  <p className="mt-0.5">{t("research.gate_3_desc")}</p>
                </div>
                <div className="p-2.5 bg-surface rounded border border-border">
                  <span className="font-bold text-text-1">Gate 4: {t("research.gate_4_title")}</span>
                  <p className="mt-0.5">{t("research.gate_4_desc")}</p>
                </div>
                <div className="p-2.5 bg-surface rounded border border-border">
                  <span className="font-bold text-text-1">Gate 5: {t("research.gate_5_title")}</span>
                  <p className="mt-0.5">{t("research.gate_5_desc")}</p>
                </div>
                <div className="p-2.5 bg-surface rounded border border-border">
                  <span className="font-bold text-text-1">Gate 6: {t("research.gate_6_title")}</span>
                  <p className="mt-0.5">{t("research.gate_6_desc")}</p>
                </div>
                <div className="p-2.5 bg-surface rounded border border-border">
                  <span className="font-bold text-text-1">Gate 7: {t("research.gate_7_title")}</span>
                  <p className="mt-0.5">{t("research.gate_7_desc")}</p>
                </div>
                <div className="p-2.5 bg-surface rounded border border-border">
                  <span className="font-bold text-text-1">Gate 8: {t("research.gate_8_title")}</span>
                  <p className="mt-0.5">{t("research.gate_8_desc")}</p>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Tab 8: Execution & Risk Management */}
      {activeTab === "execution_risk" && (
        <div className="space-y-6 animate-in fade-in duration-200">
          <div className="card-panel space-y-4">
            <div className="flex items-center gap-2 border-b border-border pb-3">
              <Radio className="w-4 h-4 text-pos" />
              <h2 className="text-sm font-bold text-text-1">{t("docs.exec_risk_title")}</h2>
            </div>
            <p className="text-xs text-text-2 leading-relaxed">
              {t("docs.exec_risk_intro")}
            </p>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-xs pt-2">
              <div className="p-4 bg-surface-2 border border-border rounded space-y-2">
                <div className="font-bold text-pos">{t("tooltips.bucket_ledger_title")}</div>
                <p className="text-[11px] text-text-3 leading-relaxed">
                  {t("tooltips.bucket_ledger_desc")}
                </p>
              </div>

              <div className="p-4 bg-surface-2 border border-border rounded space-y-2">
                <div className="font-bold text-neg">{t("tooltips.killswitch_title")}</div>
                <p className="text-[11px] text-text-3 leading-relaxed">
                  {t("tooltips.killswitch_desc")}
                </p>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Tab 9: Financial Glossary */}
      {activeTab === "glossary" && (
        <div className="space-y-6 animate-in fade-in duration-200">
          <div className="card-panel space-y-4">
            <div className="flex items-center gap-2 border-b border-border pb-3">
              <BookOpen className="w-4 h-4 text-pos" />
              <h2 className="text-sm font-bold text-text-1">{t("docs.glossary_title")}</h2>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3 text-xs pt-1">
              <div className="p-3 bg-surface-2 border border-border rounded space-y-1">
                <div className="font-bold text-pos">{t("tooltips.cagr_title")}</div>
                <p className="text-[11px] text-text-3 leading-relaxed">{t("tooltips.cagr_desc")}</p>
              </div>
              <div className="p-3 bg-surface-2 border border-border rounded space-y-1">
                <div className="font-bold text-pos">{t("tooltips.sharpe_title")}</div>
                <p className="text-[11px] text-text-3 leading-relaxed">{t("tooltips.sharpe_desc")}</p>
              </div>
              <div className="p-3 bg-surface-2 border border-border rounded space-y-1">
                <div className="font-bold text-pos">{t("tooltips.sortino_title")}</div>
                <p className="text-[11px] text-text-3 leading-relaxed">{t("tooltips.sortino_desc")}</p>
              </div>
              <div className="p-3 bg-surface-2 border border-border rounded space-y-1">
                <div className="font-bold text-neg">{t("tooltips.max_dd_title")}</div>
                <p className="text-[11px] text-text-3 leading-relaxed">{t("tooltips.max_dd_desc")}</p>
              </div>
              <div className="p-3 bg-surface-2 border border-border rounded space-y-1">
                <div className="font-bold text-pos">{t("tooltips.calmar_title")}</div>
                <p className="text-[11px] text-text-3 leading-relaxed">{t("tooltips.calmar_desc")}</p>
              </div>
              <div className="p-3 bg-surface-2 border border-border rounded space-y-1">
                <div className="font-bold text-pos">{t("tooltips.win_rate_title")}</div>
                <p className="text-[11px] text-text-3 leading-relaxed">{t("tooltips.win_rate_desc")}</p>
              </div>
              <div className="p-3 bg-surface-2 border border-border rounded space-y-1">
                <div className="font-bold text-pos">{t("tooltips.profit_factor_title")}</div>
                <p className="text-[11px] text-text-3 leading-relaxed">{t("tooltips.profit_factor_desc")}</p>
              </div>
              <div className="p-3 bg-surface-2 border border-border rounded space-y-1">
                <div className="font-bold text-pos">{t("tooltips.expectancy_title")}</div>
                <p className="text-[11px] text-text-3 leading-relaxed">{t("tooltips.expectancy_desc")}</p>
              </div>
              <div className="p-3 bg-surface-2 border border-border rounded space-y-1">
                <div className="font-bold text-info">{t("tooltips.dsr_title")}</div>
                <p className="text-[11px] text-text-3 leading-relaxed">{t("tooltips.dsr_desc")}</p>
              </div>
              <div className="p-3 bg-surface-2 border border-border rounded space-y-1">
                <div className="font-bold text-info">{t("tooltips.pbo_title")}</div>
                <p className="text-[11px] text-text-3 leading-relaxed">{t("tooltips.pbo_desc")}</p>
              </div>
              <div className="p-3 bg-surface-2 border border-border rounded space-y-1">
                <div className="font-bold text-pos">{t("tooltips.roic_title")}</div>
                <p className="text-[11px] text-text-3 leading-relaxed">{t("tooltips.roic_desc")}</p>
              </div>
              <div className="p-3 bg-surface-2 border border-border rounded space-y-1">
                <div className="font-bold text-info">{t("tooltips.sloan_accrual_title")}</div>
                <p className="text-[11px] text-text-3 leading-relaxed">{t("tooltips.sloan_accrual_desc")}</p>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
