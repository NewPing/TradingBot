"use client";

import { useEffect, useState, use } from "react";
import Link from "next/link";
import { api, EquityPoint, Run, RunTrade } from "@/lib/api";
import { MetricCard } from "@/components/MetricCard";
import { ChartCanvas } from "@/components/ChartCanvas";
import { InfoTooltip } from "@/components/Tooltip";
import { useTranslation } from "@/i18n";
import {
  ArrowLeft,
  ShieldCheck,
  Terminal,
  Layers,
  TrendingUp,
  DollarSign,
  Activity,
  Filter,
} from "lucide-react";

export default function RunDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const { t } = useTranslation();
  const resolvedParams = use(params);
  const runId = resolvedParams.id;

  const [run, setRun] = useState<Run | null>(null);
  const [equity, setEquity] = useState<EquityPoint[]>([]);
  const [trades, setTrades] = useState<RunTrade[]>([]);
  const [symbolFilter, setSymbolFilter] = useState<string>("ALL");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    Promise.all([
      api.getRun(runId),
      api.getRunEquity(runId),
      api.getRunTrades(runId),
    ]).then(([r, eq, tr]) => {
      setRun(r);
      setEquity(eq);
      setTrades(tr);
      setLoading(false);
    });
  }, [runId]);

  if (loading) {
    return (
      <div className="py-16 text-center text-xs font-mono text-text-3">
        {t("common.loading")}
      </div>
    );
  }

  if (!run) {
    return (
      <div className="card-panel py-16 text-center space-y-4">
        <div className="text-sm font-mono text-neg">{t("common.error")}: {runId}</div>
        <Link href="/" className="btn-terminal">
          &larr; {t("run_detail.return_overview")}
        </Link>
      </div>
    );
  }

  const m = run.summary_metrics || {};
  const cagr = Number(m.cagr ?? 0);
  const sharpe = Number(m.sharpe ?? 0);
  const sortino = Number(m.sortino ?? 0);
  const maxDd = Number(m.max_drawdown ?? 0);
  const calmar = Number(m.calmar ?? 0);
  const winRate = Number(m.win_rate ?? 0);
  const profitFactor = Number(m.profit_factor ?? 0);
  const expectancy = Number(m.expectancy_pct ?? 0);

  const equityChartData = equity.map((p) => ({ ts: p.ts, value: p.total_equity }));
  const drawdownChartData = equity.map((p) => ({ ts: p.ts, value: p.drawdown * 100 }));

  const symbols = ["ALL", ...Array.from(new Set(trades.map((t) => t.symbol)))];
  const filteredTrades =
    symbolFilter === "ALL" ? trades : trades.filter((t) => t.symbol === symbolFilter);

  return (
    <div className="space-y-6">
      {/* Top Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-border pb-5">
        <div className="space-y-1">
          <Link
            href="/"
            className="text-text-3 hover:text-text-1 text-xs font-mono flex items-center gap-1 mb-2"
          >
            <ArrowLeft className="w-3.5 h-3.5" />
            <span>&larr; {t("overview.title")}</span>
          </Link>
          <div className="flex items-center gap-3">
            <h1 className="text-xl font-bold font-mono tracking-tight text-text-1">{run.id}</h1>
            <span className="terminal-badge bg-surface-2 border-border text-pos">{run.status}</span>
            <span className="terminal-badge bg-surface-2 border-border text-text-2">{run.mode}</span>
          </div>
          <p className="text-xs text-text-2 font-mono">
            {t("overview.col_strategy")}: <span className="text-text-1 font-semibold">{run.strategy_version_id}</span> ·
            {t("run_detail.backtest_period")}: {new Date(run.start_ts).toLocaleDateString()} &rarr;{" "}
            {new Date(run.end_ts).toLocaleDateString()}
          </p>
        </div>
      </div>

      {/* KPI Metrics Panel */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
        <MetricCard
          label={t("overview.col_cagr")}
          value={`${(cagr * 100).toFixed(2)}%`}
          direction={cagr >= 0 ? "pos" : "neg"}
          tooltip={t("tooltips.cagr_desc")}
          tooltipTitle={t("tooltips.cagr_title")}
        />
        <MetricCard
          label={t("overview.col_sharpe")}
          value={sharpe.toFixed(2)}
          direction={sharpe >= 1.0 ? "pos" : sharpe < 0 ? "neg" : "neutral"}
          tooltip={t("tooltips.sharpe_desc")}
          tooltipTitle={t("tooltips.sharpe_title")}
        />
        <MetricCard
          label={t("overview.col_max_dd")}
          value={`${(maxDd * 100).toFixed(2)}%`}
          direction={maxDd < 0.15 ? "pos" : "neg"}
          tooltip={t("tooltips.max_dd_desc")}
          tooltipTitle={t("tooltips.max_dd_title")}
        />
        <MetricCard
          label={t("overview.col_win_rate")}
          value={`${(winRate * 100).toFixed(1)}%`}
          subValue={`${trades.length} ${t("run_detail.total_trades_count")}`}
          tooltip={t("tooltips.win_rate_desc")}
          tooltipTitle={t("tooltips.win_rate_title")}
        />
        <MetricCard
          label={t("compare.sortino_lbl")}
          value={sortino.toFixed(2)}
          tooltip={t("tooltips.sortino_desc")}
          tooltipTitle={t("tooltips.sortino_title")}
        />
        <MetricCard
          label={t("compare.calmar_lbl")}
          value={calmar.toFixed(2)}
          tooltip={t("tooltips.calmar_desc")}
          tooltipTitle={t("tooltips.calmar_title")}
        />
        <MetricCard
          label={t("compare.profit_factor_lbl")}
          value={profitFactor.toFixed(2)}
          direction={profitFactor >= 1.2 ? "pos" : profitFactor < 1.0 ? "neg" : "neutral"}
          tooltip={t("tooltips.profit_factor_desc")}
          tooltipTitle={t("tooltips.profit_factor_title")}
        />
        <MetricCard
          label={t("compare.expectancy_lbl")}
          value={`${(expectancy * 100).toFixed(2)}%`}
          direction={expectancy >= 0 ? "pos" : "neg"}
          tooltip={t("tooltips.expectancy_desc")}
          tooltipTitle={t("tooltips.expectancy_title")}
        />
      </div>

      {/* Charts: Equity + Drawdown */}
      <div className="grid grid-cols-1 gap-6">
        <ChartCanvas
          data={equityChartData}
          label={t("run_detail.equity_curve_chart")}
          height={240}
          color="#22c55e"
          formatValue={(v) => `$${v.toLocaleString(undefined, { maximumFractionDigits: 0 })}`}
        />
        <ChartCanvas
          data={drawdownChartData}
          label={t("run_detail.drawdown_chart")}
          height={140}
          color="#ef4444"
          isDrawdown={true}
          formatValue={(v) => `${v.toFixed(2)}%`}
        />
      </div>

      {/* Trade Blotter */}
      <div className="card-panel space-y-4">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
          <div className="flex items-center gap-2">
            <Activity className="w-4 h-4 text-pos" />
            <span className="text-xs font-mono font-semibold text-text-1">{t("run_detail.blotter_title")}</span>
            <span className="text-[11px] font-mono text-text-3">({filteredTrades.length} {t("run_detail.trades_count")})</span>
          </div>

          {/* Symbol Filter */}
          <div className="flex items-center gap-1.5 overflow-x-auto">
            {symbols.slice(0, 8).map((sym) => (
              <button
                key={sym}
                onClick={() => setSymbolFilter(sym)}
                className={`px-2.5 py-0.5 rounded text-[11px] font-mono transition-all ${
                  symbolFilter === sym
                    ? "bg-surface-2 text-pos border border-border font-semibold"
                    : "text-text-3 hover:text-text-1 border border-transparent"
                }`}
              >
                {sym === "ALL" ? t("versions.filter_all") : sym}
              </button>
            ))}
          </div>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs font-mono">
            <thead>
              <tr className="border-b border-border text-text-3 text-[10px] uppercase">
                <th className="pb-3 pl-2">{t("common.symbol")}</th>
                <th className="pb-3">{t("common.side")}</th>
                <th className="pb-3">{t("run_detail.entry_time")}</th>
                <th className="pb-3">{t("run_detail.exit_time")}</th>
                <th className="pb-3">{t("run_detail.entry_px")}</th>
                <th className="pb-3">{t("run_detail.exit_px")}</th>
                <th className="pb-3">{t("common.qty")}</th>
                <th className="pb-3">
                  <span className="inline-flex items-center">
                    {t("run_detail.net_pnl")}
                    <InfoTooltip title="Net Realized PnL" content="Profit or loss in USD after subtracting all transaction slippage and SEC/FINRA regulatory commissions." />
                  </span>
                </th>
                <th className="pb-3">
                  <span className="inline-flex items-center">
                    {t("run_detail.return_pct")}
                    <InfoTooltip title="Trade Return %" content="Percentage return on capital allocated to this individual trade." />
                  </span>
                </th>
                <th className="pb-3 text-right pr-2">
                  <span className="inline-flex items-center justify-end w-full">
                    {t("run_detail.exit_reason")}
                    <InfoTooltip title="Exit Trigger" content="Reason why OMS closed the position: Stop Loss, Take Profit, Regime Shift, Signal Flip, or Blackout." />
                  </span>
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border-subtle">
              {filteredTrades.length === 0 ? (
                <tr>
                  <td colSpan={10} className="py-6 text-center text-text-3">
                    {t("run_detail.no_trades_filter")}
                  </td>
                </tr>
              ) : (
                filteredTrades.map((tItem, idx) => (
                  <tr key={idx} className="hover:bg-surface-2 transition-colors">
                    <td className="py-2.5 pl-2 font-bold text-text-1">{tItem.symbol}</td>
                    <td className="py-2.5">
                      <span
                        className={`text-[10px] px-1.5 py-0.5 rounded ${
                          tItem.direction === "LONG"
                            ? "bg-surface-2 text-pos border border-border"
                            : "bg-surface-2 text-neg border border-border"
                        }`}
                      >
                        {tItem.direction}
                      </span>
                    </td>
                    <td className="py-2.5 text-text-3 text-[11px]">
                      {new Date(tItem.entry_time).toLocaleDateString()}
                    </td>
                    <td className="py-2.5 text-text-3 text-[11px]">
                      {new Date(tItem.exit_time).toLocaleDateString()}
                    </td>
                    <td className="py-2.5 text-text-2">${tItem.entry_price.toFixed(2)}</td>
                    <td className="py-2.5 text-text-2">${tItem.exit_price.toFixed(2)}</td>
                    <td className="py-2.5 text-text-2">{tItem.quantity}</td>
                    <td className="py-2.5 font-semibold">
                      <span className={tItem.pnl_net >= 0 ? "text-pos" : "text-neg"}>
                        {tItem.pnl_net >= 0 ? "+" : ""}${tItem.pnl_net.toFixed(2)}
                      </span>
                    </td>
                    <td className="py-2.5 font-semibold">
                      <span className={tItem.return_pct >= 0 ? "text-pos" : "text-neg"}>
                        {tItem.return_pct >= 0 ? "+" : ""}{(tItem.return_pct * 100).toFixed(2)}%
                      </span>
                    </td>
                    <td className="py-2.5 text-right pr-2 text-text-3 text-[11px]">
                      {tItem.exit_reason}
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* Reproducibility Footer (Hard Invariant 8) */}
      <div className="card-panel border-t-2 border-t-border space-y-4">
        <div className="flex items-center gap-2">
          <ShieldCheck className="w-4 h-4 text-pos" />
          <span className="text-xs font-mono font-semibold text-text-1 uppercase tracking-wider">
            {t("run_detail.reproducibility_title")}
          </span>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4 text-xs font-mono">
          <div className="bg-surface-2 border border-border rounded p-3">
            <div className="text-[10px] text-text-3 uppercase flex items-center justify-between">
              <span>{t("run_detail.git_sha")}</span>
              <InfoTooltip
                title={t("tooltips.git_sha_title")}
                content={t("tooltips.git_sha_desc")}
              />
            </div>
            <div className="text-text-1 font-semibold mt-1">{run.git_sha}</div>
          </div>
          <div className="bg-surface-2 border border-border rounded p-3">
            <div className="text-[10px] text-text-3 uppercase flex items-center justify-between">
              <span>{t("run_detail.spec_hash")}</span>
              <InfoTooltip
                title={t("tooltips.spec_hash_title")}
                content={t("tooltips.spec_hash_desc")}
              />
            </div>
            <div className="text-text-1 font-semibold mt-1">{run.spec_hash}</div>
          </div>
          <div className="bg-surface-2 border border-border rounded p-3">
            <div className="text-[10px] text-text-3 uppercase flex items-center justify-between">
              <span>{t("run_detail.cost_model_hash")}</span>
              <InfoTooltip
                title={t("tooltips.cost_model_title")}
                content={t("tooltips.cost_model_desc")}
              />
            </div>
            <div className="text-text-1 font-semibold mt-1">{run.cost_model_hash}</div>
          </div>
          <div className="bg-surface-2 border border-border rounded p-3">
            <div className="text-[10px] text-text-3 uppercase flex items-center justify-between">
              <span>{t("tooltips.data_snapshot_title")}</span>
              <InfoTooltip
                title={t("tooltips.data_snapshot_title")}
                content={t("tooltips.data_snapshot_desc")}
              />
            </div>
            <div className="text-text-1 font-semibold mt-1">{run.data_snapshot_id}</div>
          </div>
          <div className="bg-surface-2 border border-border rounded p-3">
            <div className="text-[10px] text-text-3 uppercase flex items-center justify-between">
              <span>{t("run_detail.seed")}</span>
              <InfoTooltip
                title={t("tooltips.random_seed_title")}
                content={t("tooltips.random_seed_desc")}
              />
            </div>
            <div className="text-text-1 font-semibold mt-1">{run.seed}</div>
          </div>
          <div className="bg-surface-2 border border-border rounded p-3">
            <div className="text-[10px] text-text-3 uppercase flex items-center justify-between">
              <span>{t("run_detail.lib_versions")}</span>
              <InfoTooltip
                title={t("tooltips.lib_versions_title")}
                content={t("tooltips.lib_versions_desc")}
              />
            </div>
            <div className="text-text-2 mt-1 text-[11px] truncate">
              {Object.entries(run.lib_versions || {})
                .map(([k, v]) => `${k}:${v}`)
                .join(" · ")}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
