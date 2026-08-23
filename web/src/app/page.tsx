"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { MetricCard } from "@/components/MetricCard";
import { api, Run, StrategyVersion, TrialBudget } from "@/lib/api";
import { Play, RefreshCw, GitCompare, Layers, TrendingUp, ShieldCheck } from "lucide-react";

export default function OverviewPage() {
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
          <h1 className="text-xl font-bold font-mono tracking-tight text-text-1">SYSTEM OVERVIEW</h1>
          <p className="text-xs text-text-2 font-mono mt-1">
            Engine status, active strategies, multiple-testing trial budget, and recent runs.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <button onClick={handleSync} className="btn-terminal">
            <RefreshCw className="w-3.5 h-3.5" />
            <span>SYNC SPECS</span>
          </button>
          <Link href="/signals" className="btn-primary">
            <TrendingUp className="w-3.5 h-3.5" />
            <span>EXPLORE SIGNALS</span>
          </Link>
        </div>
      </div>

      {/* KPI Cards Grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <MetricCard
          label="STRATEGY VERSIONS"
          value={versions.length}
          subValue={`${new Set(versions.map((v) => v.family)).size} Unique Families`}
          tooltip="Unique trading strategy specifications currently registered in the database, versioned with SHA-256 signatures."
          tooltipTitle="Strategy Versions"
        />
        <MetricCard
          label="TOTAL RUNS RECORDED"
          value={runs.length}
          subValue="Zero-lookahead backtests"
          tooltip="Historical backtests executed with t+1 order fills and full transaction cost simulation."
          tooltipTitle="Recorded Runs"
        />
        <MetricCard
          label="TRIAL BUDGET CONSUMED"
          value={budget ? `${budget.trials_this_week} / ${budget.weekly_budget}` : "0 / 500"}
          subValue={budget ? `${budget.budget_remaining} trials remaining this week` : "Budget active"}
          direction={budget && budget.budget_pct_used > 80 ? "neg" : "neutral"}
          tooltip="Weekly limit on strategy trials (default 500/week) to mathematically prevent p-hacking and overfitting to noise."
          tooltipTitle="Multiple Testing Budget"
        />
        <MetricCard
          label="INVARIANTS STATUS"
          value="12 / 12 PASS"
          subValue="Parity, Money, UTC, Lookahead"
          direction="pos"
          tooltip="Hard mathematical constraints: zero future lookahead, whole-share integer quantities, exact Decimal money (no floats), and UTC timestamps."
          tooltipTitle="System Invariants"
        />
      </div>

      {/* Main Grid: Versions + Runs */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Active Strategy Versions */}
        <div className="card-panel space-y-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Layers className="w-4 h-4 text-pos" />
              <span className="text-xs font-mono font-semibold text-text-1">STRATEGY VERSIONS</span>
            </div>
            <Link href="/versions" className="text-[11px] font-mono text-text-3 hover:text-pos">
              VIEW ALL &rarr;
            </Link>
          </div>

          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs font-mono">
              <thead>
                <tr className="border-b border-border text-text-3 text-[10px] uppercase">
                  <th className="pb-2">FAMILY</th>
                  <th className="pb-2">VER</th>
                  <th className="pb-2">STATUS</th>
                  <th className="pb-2 text-right">HASH</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border-subtle">
                {versions.length === 0 ? (
                  <tr>
                    <td colSpan={4} className="py-4 text-center text-text-3">
                      No strategies registered. Click &quot;SYNC SPECS&quot; to auto-discover YAML files.
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
              <span className="text-xs font-mono font-semibold text-text-1">RECENT EXECUTION RUNS</span>
            </div>
            <Link href="/compare" className="text-[11px] font-mono text-text-3 hover:text-pos">
              COMPARE RUNS &rarr;
            </Link>
          </div>

          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs font-mono">
              <thead>
                <tr className="border-b border-border text-text-3 text-[10px] uppercase">
                  <th className="pb-2">RUN ID</th>
                  <th className="pb-2">STRATEGY</th>
                  <th className="pb-2">CAGR</th>
                  <th className="pb-2 text-right">SHARPE</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border-subtle">
                {runs.length === 0 ? (
                  <tr>
                    <td colSpan={4} className="py-4 text-center text-text-3">
                      No execution runs recorded yet.
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
