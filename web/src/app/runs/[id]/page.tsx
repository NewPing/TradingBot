"use client";

import { useEffect, useState, use } from "react";
import Link from "next/link";
import { api, EquityPoint, Run, RunTrade } from "@/lib/api";
import { MetricCard } from "@/components/MetricCard";
import { ChartCanvas } from "@/components/ChartCanvas";
import { InfoTooltip } from "@/components/Tooltip";
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
        Loading execution run data...
      </div>
    );
  }

  if (!run) {
    return (
      <div className="card-panel py-16 text-center space-y-4">
        <div className="text-sm font-mono text-neg">Execution run &quot;{runId}&quot; not found.</div>
        <Link href="/" className="btn-terminal">
          &larr; Return to Overview
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
            <span>BACK TO RUNS</span>
          </Link>
          <div className="flex items-center gap-3">
            <h1 className="text-xl font-bold font-mono tracking-tight text-text-1">{run.id}</h1>
            <span className="terminal-badge bg-surface-2 border-border text-pos">{run.status}</span>
            <span className="terminal-badge bg-surface-2 border-border text-text-2">{run.mode}</span>
          </div>
          <p className="text-xs text-text-2 font-mono">
            Strategy Version: <span className="text-text-1 font-semibold">{run.strategy_version_id}</span> ·
            Timeframe: {new Date(run.start_ts).toLocaleDateString()} &rarr;{" "}
            {new Date(run.end_ts).toLocaleDateString()}
          </p>
        </div>
      </div>

      {/* KPI Metrics Panel */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
        <MetricCard
          label="CAGR"
          value={`${(cagr * 100).toFixed(2)}%`}
          direction={cagr >= 0 ? "pos" : "neg"}
          tooltip="Compound Annual Growth Rate — The smoothed annual geometric return rate of the portfolio."
          tooltipTitle="CAGR"
        />
        <MetricCard
          label="SHARPE RATIO"
          value={sharpe.toFixed(2)}
          direction={sharpe >= 1.0 ? "pos" : sharpe < 0 ? "neg" : "neutral"}
          tooltip="Risk-adjusted performance measure: excess return above zero divided by annual volatility. Values >1.0 are good, >2.0 are exceptional."
          tooltipTitle="Sharpe Ratio"
        />
        <MetricCard
          label="MAX DRAWDOWN"
          value={`${(maxDd * 100).toFixed(2)}%`}
          direction={maxDd < 0.15 ? "pos" : "neg"}
          tooltip="The maximum percentage drop from the highest equity peak to the lowest trough during the backtest."
          tooltipTitle="Maximum Drawdown"
        />
        <MetricCard
          label="WIN RATE"
          value={`${(winRate * 100).toFixed(1)}%`}
          subValue={`${trades.length} Total Trades`}
          tooltip="The percentage of closed trades that generated a positive net dollar return."
          tooltipTitle="Win Rate"
        />
        <MetricCard
          label="SORTINO RATIO"
          value={sortino.toFixed(2)}
          tooltip="Downside risk-adjusted metric: penalizes only negative return variance, ignoring upside jumps."
          tooltipTitle="Sortino Ratio"
        />
        <MetricCard
          label="CALMAR RATIO"
          value={calmar.toFixed(2)}
          tooltip="CAGR divided by Max Drawdown. Quantifies return achieved per unit of worst drop."
          tooltipTitle="Calmar Ratio"
        />
        <MetricCard
          label="PROFIT FACTOR"
          value={profitFactor.toFixed(2)}
          direction={profitFactor >= 1.2 ? "pos" : profitFactor < 1.0 ? "neg" : "neutral"}
          tooltip="Total gross winning dollars divided by total gross losing dollars (>1.0 indicates profitability)."
          tooltipTitle="Profit Factor"
        />
        <MetricCard
          label="EXPECTANCY"
          value={`${(expectancy * 100).toFixed(2)}%`}
          direction={expectancy >= 0 ? "pos" : "neg"}
          tooltip="Expected percentage gain per dollar placed in a trade across wins and losses."
          tooltipTitle="Trade Expectancy"
        />
      </div>

      {/* Charts: Equity + Drawdown */}
      <div className="grid grid-cols-1 gap-6">
        <ChartCanvas
          data={equityChartData}
          label="Portfolio Equity Curve ($)"
          height={240}
          color="#22c55e"
          formatValue={(v) => `$${v.toLocaleString(undefined, { maximumFractionDigits: 0 })}`}
        />
        <ChartCanvas
          data={drawdownChartData}
          label="Underwater Drawdown (%)"
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
            <span className="text-xs font-mono font-semibold text-text-1">TRADE BLOTTER</span>
            <span className="text-[11px] font-mono text-text-3">({filteredTrades.length} trades)</span>
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
                {sym}
              </button>
            ))}
          </div>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs font-mono">
            <thead>
              <tr className="border-b border-border text-text-3 text-[10px] uppercase">
                <th className="pb-3 pl-2">SYMBOL</th>
                <th className="pb-3">SIDE</th>
                <th className="pb-3">ENTRY</th>
                <th className="pb-3">EXIT</th>
                <th className="pb-3">ENTRY PX</th>
                <th className="pb-3">EXIT PX</th>
                <th className="pb-3">QTY</th>
                <th className="pb-3">PNL ($)</th>
                <th className="pb-3">RETURN</th>
                <th className="pb-3 text-right pr-2">REASON</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border-subtle">
              {filteredTrades.length === 0 ? (
                <tr>
                  <td colSpan={10} className="py-6 text-center text-text-3">
                    No trades executed in this run for the active filter.
                  </td>
                </tr>
              ) : (
                filteredTrades.map((t, idx) => (
                  <tr key={idx} className="hover:bg-surface-2 transition-colors">
                    <td className="py-2.5 pl-2 font-bold text-text-1">{t.symbol}</td>
                    <td className="py-2.5">
                      <span
                        className={`text-[10px] px-1.5 py-0.5 rounded ${
                          t.direction === "LONG"
                            ? "bg-surface-2 text-pos border border-border"
                            : "bg-surface-2 text-neg border border-border"
                        }`}
                      >
                        {t.direction}
                      </span>
                    </td>
                    <td className="py-2.5 text-text-3 text-[11px]">
                      {new Date(t.entry_time).toLocaleDateString()}
                    </td>
                    <td className="py-2.5 text-text-3 text-[11px]">
                      {new Date(t.exit_time).toLocaleDateString()}
                    </td>
                    <td className="py-2.5 text-text-2">${t.entry_price.toFixed(2)}</td>
                    <td className="py-2.5 text-text-2">${t.exit_price.toFixed(2)}</td>
                    <td className="py-2.5 text-text-2">{t.quantity}</td>
                    <td className="py-2.5 font-semibold">
                      <span className={t.pnl_net >= 0 ? "text-pos" : "text-neg"}>
                        {t.pnl_net >= 0 ? "+" : ""}${t.pnl_net.toFixed(2)}
                      </span>
                    </td>
                    <td className="py-2.5 font-semibold">
                      <span className={t.return_pct >= 0 ? "text-pos" : "text-neg"}>
                        {t.return_pct >= 0 ? "+" : ""}{(t.return_pct * 100).toFixed(2)}%
                      </span>
                    </td>
                    <td className="py-2.5 text-right pr-2 text-text-3 text-[11px]">
                      {t.exit_reason}
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
            REPRODUCIBILITY FOOTER (HARD INVARIANT 8)
          </span>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4 text-xs font-mono">
          <div className="bg-surface-2 border border-border rounded p-3">
            <div className="text-[10px] text-text-3 uppercase flex items-center justify-between">
              <span>GIT COMMIT SHA</span>
              <InfoTooltip
                title="Git Commit SHA"
                content="The exact git commit of the engine codebase used to run this backtest."
              />
            </div>
            <div className="text-text-1 font-semibold mt-1">{run.git_sha}</div>
          </div>
          <div className="bg-surface-2 border border-border rounded p-3">
            <div className="text-[10px] text-text-3 uppercase flex items-center justify-between">
              <span>SPECIFICATION SHA-256</span>
              <InfoTooltip
                title="Strategy Hash"
                content="Cryptographic fingerprint of the strategy YAML parameters."
              />
            </div>
            <div className="text-text-1 font-semibold mt-1">{run.spec_hash}</div>
          </div>
          <div className="bg-surface-2 border border-border rounded p-3">
            <div className="text-[10px] text-text-3 uppercase flex items-center justify-between">
              <span>COST MODEL SIGNATURE</span>
              <InfoTooltip
                title="Cost Model"
                content="Pessimistic transaction cost configuration (spread, market-impact slippage, SEC and FINRA fees, commissions)."
              />
            </div>
            <div className="text-text-1 font-semibold mt-1">{run.cost_model_hash}</div>
          </div>
          <div className="bg-surface-2 border border-border rounded p-3">
            <div className="text-[10px] text-text-3 uppercase flex items-center justify-between">
              <span>DATA SNAPSHOT ID</span>
              <InfoTooltip
                title="Data Snapshot"
                content="Immutable historical Parquet snapshot dataset ensuring byte-identical reproducibility."
              />
            </div>
            <div className="text-text-1 font-semibold mt-1">{run.data_snapshot_id}</div>
          </div>
          <div className="bg-surface-2 border border-border rounded p-3">
            <div className="text-[10px] text-text-3 uppercase flex items-center justify-between">
              <span>EXECUTION RANDOM SEED</span>
              <InfoTooltip
                title="Random Seed"
                content="Deterministic pseudo-random seed (e.g. 42) guaranteeing reproducible order tie-breaking."
              />
            </div>
            <div className="text-text-1 font-semibold mt-1">{run.seed}</div>
          </div>
          <div className="bg-surface-2 border border-border rounded p-3">
            <div className="text-[10px] text-text-3 uppercase flex items-center justify-between">
              <span>SYSTEM & RUNTIME VERSIONS</span>
              <InfoTooltip
                title="Library Versions"
                content="Captured runtime package versions (Polars, NumPy, SQLAlchemy, etc.) recorded for forensic audit."
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
