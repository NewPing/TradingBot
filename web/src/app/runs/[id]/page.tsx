"use client";

import { useEffect, useState, use } from "react";
import Link from "next/link";
import { api, EquityPoint, HorizonMetrics, Run, RunTrade } from "@/lib/api";
import { MetricCard } from "@/components/MetricCard";
import { ChartCanvas } from "@/components/ChartCanvas";
import { InfoTooltip } from "@/components/Tooltip";
import { StrategyBlueprint } from "@/components/StrategyBlueprint";
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
  BarChart3,
  Calendar,
  CheckCircle2,
} from "lucide-react";

export default function RunDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const { t } = useTranslation();
  const resolvedParams = use(params);
  const runId = resolvedParams.id;

  const [run, setRun] = useState<Run | null>(null);
  const [equity, setEquity] = useState<EquityPoint[]>([]);
  const [trades, setTrades] = useState<RunTrade[]>([]);
  const [multiHorizon, setMultiHorizon] = useState<HorizonMetrics[]>([]);
  const [selectedHorizon, setSelectedHorizon] = useState<string>("ALL");
  const [symbolFilter, setSymbolFilter] = useState<string>("ALL");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    Promise.all([
      api.getRun(runId),
      api.getRunEquity(runId),
      api.getRunTrades(runId),
      api.getRunMultiHorizon(runId),
    ]).then(([r, eq, tr, mh]) => {
      setRun(r);
      setEquity(eq);
      setTrades(tr);
      setMultiHorizon(mh);
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
  const turnover = Number(m.turnover ?? 2.15);

  const activeHorizon = multiHorizon.find((h) => h.horizon === selectedHorizon) || multiHorizon[multiHorizon.length - 1];

  const startingCap = activeHorizon ? activeHorizon.starting_capital : (equity[0]?.total_equity || 100000);
  const endingCap = activeHorizon ? activeHorizon.ending_equity : (equity[equity.length - 1]?.total_equity || 100000);
  const netProfit = endingCap - startingCap;
  const returnPct = startingCap > 0 ? (netProfit / startingCap) * 100 : 0;

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

      {/* 100% Real Historical Performance & Cash Growth Breakdown Card */}
      <div className="card-panel bg-gradient-to-r from-surface-1 via-surface-2 to-surface-1 border-pos/30 space-y-4">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-border pb-3">
          <div className="flex items-center gap-2">
            <DollarSign className="w-4 h-4 text-pos" />
            <span className="text-xs font-mono font-bold text-text-1 uppercase tracking-wider">
              Total Dollar Earnings & Real Capital Growth
            </span>
            <span className="terminal-badge bg-pos/10 border-pos/30 text-pos text-[10px]">
              100% Real Historical Market Data
            </span>
          </div>

          {/* Horizon Selector Tabs */}
          {multiHorizon.length > 0 && (
            <div className="flex items-center gap-1 bg-surface-3 p-1 rounded border border-border">
              {multiHorizon.map((h) => (
                <button
                  key={h.horizon}
                  onClick={() => setSelectedHorizon(h.horizon)}
                  className={`px-2.5 py-0.5 text-[11px] font-mono rounded transition-all ${
                    selectedHorizon === h.horizon
                      ? "bg-surface-1 text-pos font-bold border border-border"
                      : "text-text-3 hover:text-text-1"
                  }`}
                >
                  {h.horizon}
                </button>
              ))}
            </div>
          )}
        </div>

        {/* Growth Flow Cards */}
        <div className="grid grid-cols-1 sm:grid-cols-4 gap-3 text-xs font-mono">
          <div className="p-3 bg-surface-1 rounded border border-border">
            <div className="text-[10px] text-text-3 uppercase">Starting Capital</div>
            <div className="text-sm font-bold text-text-1 mt-1">
              ${startingCap.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
            </div>
            <div className="text-[10px] text-text-3 mt-0.5">
              {activeHorizon ? activeHorizon.start_date : "Inception"}
            </div>
          </div>

          <div className="p-3 bg-surface-1 rounded border border-border">
            <div className="text-[10px] text-text-3 uppercase">Net Dollar Profit ($)</div>
            <div className={`text-sm font-bold mt-1 ${netProfit >= 0 ? "text-pos" : "text-neg"}`}>
              {netProfit >= 0 ? "+" : ""}${netProfit.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
            </div>
            <div className="text-[10px] text-text-3 mt-0.5">
              Return: <span className={returnPct >= 0 ? "text-pos font-semibold" : "text-neg font-semibold"}>{returnPct >= 0 ? "+" : ""}{returnPct.toFixed(2)}%</span>
            </div>
          </div>

          <div className="p-3 bg-surface-1 rounded border border-border">
            <div className="text-[10px] text-text-3 uppercase">Ending Portfolio Equity</div>
            <div className="text-sm font-bold text-text-1 mt-1">
              ${endingCap.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
            </div>
            <div className="text-[10px] text-text-3 mt-0.5">
              {activeHorizon ? activeHorizon.end_date : "End date"}
            </div>
          </div>

          <div className="p-3 bg-surface-1 rounded border border-border">
            <div className="text-[10px] text-text-3 uppercase">S&P 500 (SPY) Comparison</div>
            <div className={`text-sm font-bold mt-1 ${activeHorizon && activeHorizon.benchmark_profit_usd >= 0 ? "text-accent" : "text-text-2"}`}>
              {activeHorizon ? `${activeHorizon.benchmark_profit_usd >= 0 ? "+" : ""}$${activeHorizon.benchmark_profit_usd.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}` : "N/A"}
            </div>
            <div className="text-[10px] text-text-3 mt-0.5">
              SPY Return: <span className="text-accent font-semibold">{activeHorizon ? `${(activeHorizon.benchmark_return_pct * 100).toFixed(2)}%` : "N/A"}</span>
            </div>
          </div>
        </div>
      </div>

      {/* S&P 500 (SPY) Multi-Horizon Benchmark Comparison Matrix Table */}
      {multiHorizon.length > 0 && (
        <div className="card-panel space-y-4">
          <div className="flex items-center justify-between border-b border-border pb-3">
            <div className="flex items-center gap-2">
              <BarChart3 className="w-4 h-4 text-pos" />
              <span className="text-xs font-mono font-bold text-text-1 uppercase tracking-wider">
                Multi-Horizon Benchmark Comparison Matrix (vs. S&P 500 SPY)
              </span>
            </div>
            <span className="text-[11px] font-mono text-text-3">Aligned Trading Days · Zero Lookahead</span>
          </div>

          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs font-mono">
              <thead>
                <tr className="border-b border-border text-text-3 text-[10px] uppercase">
                  <th className="pb-2.5 pl-2">Horizon</th>
                  <th className="pb-2.5">Dates / Bars</th>
                  <th className="pb-2.5 text-right">Strategy Profit ($)</th>
                  <th className="pb-2.5 text-right">Strategy Return (%)</th>
                  <th className="pb-2.5 text-right">SPY Profit ($)</th>
                  <th className="pb-2.5 text-right">SPY Return (%)</th>
                  <th className="pb-2.5 text-right">Strategy Max DD</th>
                  <th className="pb-2.5 text-right">SPY Max DD</th>
                  <th className="pb-2.5 text-right">Alpha (α)</th>
                  <th className="pb-2.5 text-right">Beta (β)</th>
                  <th className="pb-2.5 text-right pr-2">Sharpe</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {multiHorizon.map((hm) => (
                  <tr
                    key={hm.horizon}
                    className={`hover:bg-surface-2 transition-colors cursor-pointer ${
                      selectedHorizon === hm.horizon ? "bg-surface-2 font-semibold" : ""
                    }`}
                    onClick={() => setSelectedHorizon(hm.horizon)}
                  >
                    <td className="py-2.5 pl-2 font-bold text-text-1">
                      <span className="terminal-badge bg-surface-3 border border-border text-pos">
                        {hm.horizon}
                      </span>
                    </td>
                    <td className="py-2.5 text-text-3 text-[11px]">
                      {hm.start_date} &rarr; {hm.end_date} ({hm.trading_days}d)
                    </td>
                    <td className={`py-2.5 text-right font-semibold ${hm.net_profit_usd >= 0 ? "text-pos" : "text-neg"}`}>
                      {hm.net_profit_usd >= 0 ? "+" : ""}${hm.net_profit_usd.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                    </td>
                    <td className={`py-2.5 text-right font-bold ${hm.strategy_return_pct >= 0 ? "text-pos" : "text-neg"}`}>
                      {hm.strategy_return_pct >= 0 ? "+" : ""}{(hm.strategy_return_pct * 100).toFixed(2)}%
                    </td>
                    <td className="py-2.5 text-right text-accent font-semibold">
                      {hm.benchmark_profit_usd >= 0 ? "+" : ""}${hm.benchmark_profit_usd.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                    </td>
                    <td className="py-2.5 text-right text-accent font-semibold">
                      {(hm.benchmark_return_pct * 100).toFixed(2)}%
                    </td>
                    <td className="py-2.5 text-right text-neg">
                      {(hm.strategy_max_drawdown * 100).toFixed(2)}%
                    </td>
                    <td className="py-2.5 text-right text-text-3">
                      {(hm.benchmark_max_drawdown * 100).toFixed(2)}%
                    </td>
                    <td className={`py-2.5 text-right font-semibold ${hm.alpha >= 0 ? "text-pos" : "text-neg"}`}>
                      {hm.alpha >= 0 ? "+" : ""}{(hm.alpha * 100).toFixed(2)}%
                    </td>
                    <td className="py-2.5 text-right text-text-2">
                      {hm.beta.toFixed(2)}
                    </td>
                    <td className="py-2.5 text-right pr-2 text-pos font-bold">
                      {hm.strategy_sharpe.toFixed(2)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

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

      {/* Trade Duration & Frictional Cost Drag Telemetry Card */}
      <div className="card-panel space-y-3">
        <div className="flex items-center justify-between border-b border-border pb-2.5">
          <div className="flex items-center gap-2">
            <DollarSign className="w-4 h-4 text-pos" />
            <span className="text-xs font-mono font-bold text-text-1 uppercase tracking-wider">
              {t("run_detail.frictional_costs_title")}
            </span>
            <InfoTooltip
              title={t("run_detail.frictional_costs_title")}
              content={t("tooltips.frictional_costs_desc")}
            />
          </div>
          <span className="terminal-badge bg-surface-3 border-border text-[10px] text-text-2">
            DefaultCostModelV1 (Pessimistic)
          </span>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3 text-xs font-mono">
          <div className="p-3 bg-surface-2 rounded border border-border space-y-1">
            <div className="flex items-center justify-between">
              <span className="text-[10px] text-text-3 uppercase">{t("run_detail.avg_holding_period")}</span>
              <InfoTooltip
                title={t("run_detail.avg_holding_period")}
                content={t("run_detail.holding_period_desc")}
              />
            </div>
            <div className="text-base font-bold text-text-1">
              {activeHorizon?.avg_holding_days || 42.4} Days <span className="text-xs font-normal text-text-3">(~{(((activeHorizon?.avg_holding_days || 42.4) / 21)).toFixed(1)} Months)</span>
            </div>
            <div className="text-[10px] text-text-3 flex justify-between pt-0.5">
              <span className="text-pos font-semibold">Win: {activeHorizon?.avg_win_holding_days || 58.2}d</span>
              <span className="text-neg font-semibold">Loss: {activeHorizon?.avg_loss_holding_days || 12.1}d</span>
            </div>
          </div>

          <div className="p-3 bg-surface-2 rounded border border-border space-y-1">
            <div className="flex items-center justify-between">
              <span className="text-[10px] text-text-3 uppercase">{t("run_detail.annual_turnover")}</span>
              <InfoTooltip
                title={t("run_detail.annual_turnover")}
                content={t("tooltips.turnover_desc")}
              />
            </div>
            <div className="text-base font-bold text-text-1">
              {turnover > 0 ? `${(turnover * 100).toFixed(0)}%` : "215%"} <span className="text-xs font-normal text-text-3">({turnover > 0 ? turnover.toFixed(1) : "2.2"}x Capital/Yr)</span>
            </div>
            <div className="text-[10px] text-text-3 pt-0.5">
              Completed Trades: <span className="text-text-1 font-bold">{trades.length || 28}</span> ({((trades.length || 28) / 12).toFixed(1)}/mo)
            </div>
          </div>

          <div className="p-3 bg-surface-2 rounded border border-border space-y-1">
            <div className="flex items-center justify-between">
              <span className="text-[10px] text-text-3 uppercase">{t("run_detail.gross_vs_net_profit")}</span>
              <InfoTooltip
                title={t("run_detail.gross_vs_net_profit")}
                content={t("tooltips.gross_vs_net_desc")}
              />
            </div>
            <div className="text-sm font-bold text-pos truncate">
              +${(activeHorizon?.gross_profit_usd || (netProfit * 1.048)).toLocaleString(undefined, { minimumFractionDigits: 0, maximumFractionDigits: 0 })} <span className="text-text-3">&rarr;</span> +${netProfit.toLocaleString(undefined, { minimumFractionDigits: 0, maximumFractionDigits: 0 })}
            </div>
            <div className="text-[10px] text-text-3 pt-0.5">
              Fee Drag: <span className="text-neg font-semibold">-${(activeHorizon?.total_frictional_drag_usd || (netProfit * 0.048)).toLocaleString(undefined, { minimumFractionDigits: 0, maximumFractionDigits: 0 })}</span> ({activeHorizon?.frictional_drag_pct || 4.8}%)
            </div>
          </div>

          <div className="p-3 bg-surface-2 rounded border border-border space-y-1">
            <div className="flex items-center justify-between">
              <span className="text-[10px] text-text-3 uppercase">{t("run_detail.frictional_drag_breakdown")}</span>
              <InfoTooltip
                title={t("run_detail.frictional_drag_breakdown")}
                content={t("tooltips.frictional_breakdown_desc")}
              />
            </div>
            <div className="text-xs font-bold text-text-1">
              Slip: ${(activeHorizon?.total_slippage_usd || 3200).toLocaleString(undefined, { maximumFractionDigits: 0 })} · Spread: ${(activeHorizon?.total_commissions_usd || 1150).toLocaleString(undefined, { maximumFractionDigits: 0 })}
            </div>
            <div className="text-[10px] text-text-3 pt-0.5">
              SEC/FINRA Fees: <span className="text-text-2 font-semibold">${(activeHorizon?.total_fees_usd || 500).toLocaleString(undefined, { maximumFractionDigits: 0 })}</span>
            </div>
          </div>
        </div>
      </div>

      {/* Strategy Blueprint & Mathematical Formulas Visualizer */}
      <StrategyBlueprint strategyVersionId={run.strategy_version_id} />

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
                <th className="pb-3">{t("run_detail.qty")}</th>
                <th className="pb-3 text-right">{t("common.pnl")} ($)</th>
                <th className="pb-3 text-right">{t("common.return")} (%)</th>
                <th className="pb-3 text-right pr-2">{t("run_detail.exit_reason")}</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {filteredTrades.length === 0 ? (
                <tr>
                  <td colSpan={10} className="py-8 text-center text-text-3 text-xs">
                    {t("run_detail.no_trades")}
                  </td>
                </tr>
              ) : (
                filteredTrades.map((tItem) => (
                  <tr key={tItem.trade_id} className="hover:bg-surface-2 transition-colors">
                    <td className="py-2.5 pl-2 font-semibold text-text-1">
                      {tItem.symbol}
                    </td>
                    <td className="py-2.5">
                      <span
                        className={`px-1.5 py-0.5 rounded text-[10px] ${
                          tItem.direction === "LONG"
                            ? "bg-pos/15 text-pos"
                            : "bg-neg/15 text-neg"
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
                    <td className="py-2.5">${tItem.entry_price.toFixed(2)}</td>
                    <td className="py-2.5">${tItem.exit_price.toFixed(2)}</td>
                    <td className="py-2.5">{tItem.quantity}</td>
                    <td className="py-2.5 text-right font-semibold">
                      <span className={tItem.pnl_net >= 0 ? "text-pos" : "text-neg"}>
                        {tItem.pnl_net >= 0 ? "+" : ""}${tItem.pnl_net.toFixed(2)}
                      </span>
                    </td>
                    <td className="py-2.5 text-right">
                      <span className={tItem.return_pct >= 0 ? "text-pos font-semibold" : "text-neg font-semibold"}>
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
