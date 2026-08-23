"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { MetricCard } from "@/components/MetricCard";
import { InfoTooltip } from "@/components/Tooltip";
import { api, Run, StrategyVersion, TrialBudget } from "@/lib/api";
import { Play, RefreshCw, Layers, TrendingUp, Sparkles, BookOpen, ArrowRight, ShieldCheck } from "lucide-react";
import { useTranslation } from "@/i18n";
import { useWalkthrough } from "@/components/WalkthroughContext";

export default function OverviewPage() {
  const { t } = useTranslation();
  const { openWalkthrough } = useWalkthrough();
  const [versions, setVersions] = useState<StrategyVersion[]>([]);
  const [runs, setRuns] = useState<Run[]>([]);
  const [budget, setBudget] = useState<TrialBudget | null>(null);
  const [loading, setLoading] = useState(true);

  const fetchData = async () => {
    setLoading(true);
    const [vers, rns, bdg] = await Promise.all([
      api.getVersions(),
      api.getRuns(undefined, 10),
      api.getTrialBudget(),
    ]);
    setVersions(vers);
    setRuns(rns);
    setBudget(bdg);
    setLoading(false);
  };

  useEffect(() => {
    fetchData();
  }, []);

  const handleSync = async () => {
    await api.syncStrategies();
    await fetchData();
  };

  return (
    <div className="space-y-6">
      {/* Top Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-border pb-5">
        <div>
          <h1 className="text-xl font-bold font-mono tracking-tight text-text-1">
            {t("overview.title")}
          </h1>
          <p className="text-xs text-text-2 font-mono mt-1">
            {t("overview.subtitle")}
          </p>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={() => openWalkthrough(0)}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded bg-pos/10 border border-pos/40 text-pos hover:bg-pos/20 text-xs font-mono font-bold transition-all shadow-sm"
          >
            <Sparkles className="w-3.5 h-3.5" />
            <span>{t("nav.walkthrough_btn")}</span>
          </button>
          <button onClick={handleSync} className="btn-terminal">
            <RefreshCw className="w-3.5 h-3.5" />
            <span>{t("overview.sync_specs")}</span>
          </button>
          <Link href="/signals" className="btn-primary">
            <TrendingUp className="w-3.5 h-3.5" />
            <span>{t("overview.explore_signals")}</span>
          </Link>
        </div>
      </div>

      {/* Quick Orientation Banner */}
      <div className="bg-gradient-to-r from-surface to-surface-2 border border-border rounded-lg p-4 flex flex-col sm:flex-row sm:items-center justify-between gap-3 font-mono">
        <div className="space-y-1">
          <div className="flex items-center gap-2">
            <span className="text-xs font-bold text-pos flex items-center gap-1.5">
              <Sparkles className="w-3.5 h-3.5" />
              {t("overview.quick_start_title")}
            </span>
            <span className="text-[10px] px-1.5 py-0.2 rounded bg-surface border border-border text-text-3">
              L1–L4
            </span>
          </div>
          <p className="text-[11px] text-text-2">
            {t("overview.quick_start_desc")}
          </p>
        </div>

        <div className="flex items-center gap-2 shrink-0">
          <button
            onClick={() => openWalkthrough(0)}
            className="btn-primary py-1 px-3 text-xs"
          >
            <span>{t("nav.walkthrough_btn")}</span>
            <ArrowRight className="w-3.5 h-3.5 ml-1" />
          </button>
          <Link
            href="/docs"
            className="btn-terminal py-1 px-3 text-xs flex items-center gap-1.5"
          >
            <BookOpen className="w-3.5 h-3.5 text-text-3" />
            <span>{t("nav.docs")}</span>
          </Link>
        </div>
      </div>

      {/* KPI Cards Grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <MetricCard
          label={t("overview.kpi_versions")}
          value={versions.length}
          subValue={`${new Set(versions.map((v) => v.family)).size} ${t("overview.kpi_versions_sub")}`}
          tooltip={t("tooltips.strategy_versions_desc")}
          tooltipTitle={t("tooltips.strategy_versions_title")}
        />
        <MetricCard
          label={t("overview.kpi_runs")}
          value={runs.length}
          subValue={t("overview.kpi_runs_sub")}
          tooltip={t("tooltips.recorded_runs_desc")}
          tooltipTitle={t("tooltips.recorded_runs_title")}
        />
        <MetricCard
          label={t("overview.kpi_budget")}
          value={budget ? `${budget.trials_this_week} / ${budget.weekly_budget}` : "0 / 500"}
          subValue={budget ? `${budget.budget_remaining} ${t("overview.kpi_budget_remaining")}` : t("common.budget_active")}
          direction={budget && budget.budget_pct_used > 80 ? "neg" : "neutral"}
          tooltip={t("tooltips.trial_budget_desc")}
          tooltipTitle={t("tooltips.trial_budget_title")}
        />
        <MetricCard
          label={t("overview.kpi_buckets")}
          value="4 / 4"
          subValue={t("overview.kpi_buckets_sub")}
          direction="pos"
          tooltip={t("tooltips.active_buckets_desc")}
          tooltipTitle={t("tooltips.active_buckets_title")}
        />
      </div>

      {/* Main Grid: Versions + Runs */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Active Strategy Versions */}
        <div className="card-panel space-y-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Layers className="w-4 h-4 text-pos" />
              <span className="text-xs font-mono font-semibold text-text-1">
                {t("overview.strategy_families")}
              </span>
              <InfoTooltip
                title={t("tooltips.strategy_versions_title")}
                content={t("tooltips.strategy_versions_desc")}
              />
            </div>
            <Link href="/versions" className="text-[11px] font-mono text-text-3 hover:text-pos">
              {t("overview.view_lineage")} &rarr;
            </Link>
          </div>

          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs font-mono">
              <thead>
                <tr className="border-b border-border text-text-3 text-[10px] uppercase">
                  <th className="pb-2">
                    <span className="inline-flex items-center">
                      {t("overview.col_family")}
                    </span>
                  </th>
                  <th className="pb-2">
                    <span className="inline-flex items-center">
                      {t("common.version_abbr")}
                      <InfoTooltip title={t("tooltips.strategy_versions_title")} content={t("tooltips.strategy_versions_desc")} />
                    </span>
                  </th>
                  <th className="pb-2">
                    <span className="inline-flex items-center">
                      {t("common.status")}
                      <InfoTooltip title={t("tooltips.parity_title")} content={t("tooltips.parity_desc")} />
                    </span>
                  </th>
                  <th className="pb-2 text-right">
                    <span className="inline-flex items-center justify-end w-full">
                      {t("common.hash_abbr")}
                      <InfoTooltip title={t("tooltips.spec_hash_title")} content={t("tooltips.spec_hash_desc")} />
                    </span>
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border-subtle">
                {versions.length === 0 ? (
                  <tr>
                    <td colSpan={4} className="py-4 text-center text-text-3">
                      {t("common.no_data")}
                    </td>
                  </tr>
                ) : (
                  versions.slice(0, 6).map((v) => (
                    <tr key={v.id} className="hover:bg-surface-2 transition-colors">
                      <td className="py-2.5 font-medium text-text-1">{v.family}</td>
                      <td className="py-2.5 text-text-2">v{v.version}</td>
                      <td className="py-2.5">
                        <span className="terminal-badge bg-surface-2 border-border text-pos">
                          {v.status}
                        </span>
                      </td>
                      <td className="py-2.5 text-right text-text-3 text-[11px]">
                        {v.spec_hash.substring(0, 8)}
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </div>

        {/* Recent Backtest Runs */}
        <div className="card-panel space-y-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Play className="w-4 h-4 text-pos" />
              <span className="text-xs font-mono font-semibold text-text-1">
                {t("overview.recent_runs")}
              </span>
              <InfoTooltip
                title={t("tooltips.recorded_runs_title")}
                content={t("tooltips.recorded_runs_desc")}
              />
            </div>
            <Link href="/compare" className="text-[11px] font-mono text-text-3 hover:text-pos">
              {t("overview.view_all_runs")} &rarr;
            </Link>
          </div>

          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs font-mono">
              <thead>
                <tr className="border-b border-border text-text-3 text-[10px] uppercase">
                  <th className="pb-2">{t("overview.col_run_id")}</th>
                  <th className="pb-2">{t("overview.col_strategy")}</th>
                  <th className="pb-2">
                    <span className="inline-flex items-center">
                      {t("overview.col_cagr")}
                      <InfoTooltip title={t("tooltips.cagr_title")} content={t("tooltips.cagr_desc")} />
                    </span>
                  </th>
                  <th className="pb-2 text-right">
                    <span className="inline-flex items-center justify-end w-full">
                      {t("overview.col_sharpe")}
                      <InfoTooltip title={t("tooltips.sharpe_title")} content={t("tooltips.sharpe_desc")} />
                    </span>
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border-subtle">
                {runs.length === 0 ? (
                  <tr>
                    <td colSpan={4} className="py-4 text-center text-text-3">
                      {t("common.no_data")}
                    </td>
                  </tr>
                ) : (
                  runs.slice(0, 6).map((r) => {
                    const cagr = r.summary_metrics?.cagr;
                    const sharpe = r.summary_metrics?.sharpe;
                    return (
                      <tr key={r.id} className="hover:bg-surface-2 transition-colors">
                        <td className="py-2.5">
                          <Link href={`/runs/${r.id}`} className="text-text-1 hover:text-pos">
                            {r.id.substring(0, 16)}...
                          </Link>
                        </td>
                        <td className="py-2.5 text-text-2">{r.strategy_version_id}</td>
                        <td className="py-2.5 font-medium">
                          {typeof cagr === "number" ? (
                            <span className={cagr >= 0 ? "text-pos" : "text-neg"}>
                              {(cagr * 100).toFixed(1)}%
                            </span>
                          ) : (
                            "—"
                          )}
                        </td>
                        <td className="py-2.5 text-right font-medium">
                          {typeof sharpe === "number" ? sharpe.toFixed(2) : "—"}
                        </td>
                      </tr>
                    );
                  })
                )}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </div>
  );
}
