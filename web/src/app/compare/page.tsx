"use client";

import { useEffect, useState, Suspense } from "react";
import { useSearchParams } from "next/navigation";
import { api, CompareData, Run } from "@/lib/api";
import { ChartCanvas } from "@/components/ChartCanvas";
import { GitCompare, ArrowUpRight, ArrowDownRight, Layers, Play } from "lucide-react";

function CompareContent() {
  const searchParams = useSearchParams();
  const runIdsParam = searchParams.get("run_ids");

  const [availableRuns, setAvailableRuns] = useState<Run[]>([]);
  const [selectedRunIds, setSelectedRunIds] = useState<string[]>([]);
  const [compareData, setCompareData] = useState<CompareData | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    api.getRuns(undefined, 50).then((runs) => {
      setAvailableRuns(runs);
      if (runIdsParam) {
        const ids = runIdsParam.split(",").map((s) => s.trim()).filter(Boolean);
        setSelectedRunIds(ids);
      } else if (runs.length >= 2) {
        setSelectedRunIds([runs[0].id, runs[1].id]);
      } else if (runs.length === 1) {
        setSelectedRunIds([runs[0].id]);
      }
    });
  }, [runIdsParam]);

  useEffect(() => {
    if (selectedRunIds.length > 0) {
      setLoading(true);
      api.getComparison(selectedRunIds).then((data) => {
        setCompareData(data);
        setLoading(false);
      });
    }
  }, [selectedRunIds]);

  const handleToggleRun = (id: string) => {
    setSelectedRunIds((prev) =>
      prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id]
    );
  };

  const metricRows = [
    { key: "cagr", label: "CAGR (%)", format: (v: number) => `${(v * 100).toFixed(2)}%`, higherIsBetter: true },
    { key: "sharpe", label: "SHARPE RATIO", format: (v: number) => v.toFixed(2), higherIsBetter: true },
    { key: "sortino", label: "SORTINO RATIO", format: (v: number) => v.toFixed(2), higherIsBetter: true },
    { key: "max_drawdown", label: "MAX DRAWDOWN (%)", format: (v: number) => `${(v * 100).toFixed(2)}%`, higherIsBetter: false },
    { key: "calmar", label: "CALMAR RATIO", format: (v: number) => v.toFixed(2), higherIsBetter: true },
    { key: "win_rate", label: "WIN RATE (%)", format: (v: number) => `${(v * 100).toFixed(1)}%`, higherIsBetter: true },
    { key: "profit_factor", label: "PROFIT FACTOR", format: (v: number) => v.toFixed(2), higherIsBetter: true },
    { key: "expectancy_pct", label: "EXPECTANCY (%)", format: (v: number) => `${(v * 100).toFixed(2)}%`, higherIsBetter: true },
    { key: "total_trades", label: "TOTAL TRADES", format: (v: number) => Math.round(v).toString(), higherIsBetter: null },
    { key: "turnover_annual", label: "ANNUAL TURNOVER", format: (v: number) => `${v.toFixed(1)}x`, higherIsBetter: null },
  ];

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-border pb-5">
        <div>
          <h1 className="text-xl font-bold font-mono tracking-tight text-text-1">
            RUN COMPARISON MATRIX
          </h1>
          <p className="text-xs text-text-2 font-mono mt-1">
            Overlaid equity curves, drawdown underwater plots, and side-by-side performance metrics.
          </p>
        </div>
      </div>

      {/* Run Selector Chips */}
      <div className="card-panel space-y-3">
        <div className="terminal-label">SELECT RUNS TO COMPARE</div>
        <div className="flex flex-wrap gap-2">
          {availableRuns.length === 0 ? (
            <div className="text-xs font-mono text-text-3">No runs found in database.</div>
          ) : (
            availableRuns.map((r) => {
              const active = selectedRunIds.includes(r.id);
              return (
                <button
                  key={r.id}
                  onClick={() => handleToggleRun(r.id)}
                  className={`px-3 py-1.5 rounded text-xs font-mono flex items-center gap-2 transition-all ${
                    active
                      ? "bg-active border border-pos text-text-1 font-semibold"
                      : "bg-surface-2 border border-border text-text-3 hover:text-text-1 hover:border-text-3"
                  }`}
                >
                  <span className={`w-2 h-2 rounded-full ${active ? "bg-pos" : "bg-text-3"}`} />
                  <span>{r.strategy_version_id}</span>
                  <span className="text-[10px] text-text-3">({r.id.substring(0, 8)})</span>
                </button>
              );
            })
          )}
        </div>
      </div>

      {loading ? (
        <div className="py-12 text-center text-text-3 font-mono text-xs">
          Computing comparison metrics and series...
        </div>
      ) : !compareData || compareData.runs.length === 0 ? (
        <div className="card-panel py-12 text-center text-text-3 font-mono text-xs">
          Select at least one execution run above to inspect metrics.
        </div>
      ) : (
        <>
          {/* Overlaid Equity Charts */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {compareData.runs.map((r, idx) => {
              const eqPoints = compareData.equity_by_run[r.id] || [];
              const chartData = eqPoints.map((p) => ({ ts: p.ts, value: p.equity }));
              const ddData = eqPoints.map((p) => ({ ts: p.ts, value: p.drawdown * 100 }));
              const colors = ["#22c55e", "#38bdf8", "#f59e0b", "#a855f7"];
              const color = colors[idx % colors.length];

              return (
                <div key={r.id} className="space-y-4">
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-mono font-bold text-text-1">
                      {r.strategy_version_id}
                    </span>
                    <span className="text-[11px] font-mono text-text-3">
                      SNAPSHOT: {r.data_snapshot_id}
                    </span>
                  </div>
                  <ChartCanvas
                    data={chartData}
                    label={`${r.strategy_version_id} Equity ($)`}
                    height={180}
                    color={color}
                    formatValue={(v) => `$${v.toLocaleString(undefined, { maximumFractionDigits: 0 })}`}
                  />
                  <ChartCanvas
                    data={ddData}
                    label={`${r.strategy_version_id} Drawdown (%)`}
                    height={120}
                    color="#ef4444"
                    isDrawdown={true}
                    formatValue={(v) => `${v.toFixed(1)}%`}
                  />
                </div>
              );
            })}
          </div>

          {/* Metrics Diff Table */}
          <div className="card-panel space-y-3">
            <div className="terminal-label">SIDE-BY-SIDE METRICS DIFF</div>
            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs font-mono">
                <thead>
                  <tr className="border-b border-border text-text-3 text-[10px] uppercase">
                    <th className="pb-3 pl-2">METRIC</th>
                    {compareData.runs.map((r) => (
                      <th key={r.id} className="pb-3 text-right pr-4">
                        {r.strategy_version_id}
                        <div className="text-[9px] text-text-3 font-normal">
                          {r.id.substring(0, 10)}
                        </div>
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody className="divide-y divide-border-subtle">
                  {metricRows.map((row) => (
                    <tr key={row.key} className="hover:bg-surface-2 transition-colors">
                      <td className="py-2.5 pl-2 font-medium text-text-2">{row.label}</td>
                      {compareData.runs.map((r) => {
                        const val = compareData.metrics_diff[row.key]?.[r.id] ?? 0;
                        let cellClass = "text-text-1";
                        if (row.higherIsBetter === true) {
                          cellClass = val > 0 ? "text-pos" : val < 0 ? "text-neg" : "text-text-1";
                        } else if (row.higherIsBetter === false) {
                          cellClass = val < 0.2 ? "text-pos" : "text-neg";
                        }
                        return (
                          <td key={r.id} className={`py-2.5 text-right pr-4 font-semibold ${cellClass}`}>
                            {row.format(val)}
                          </td>
                        );
                      })}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>

          {/* Reproducibility Comparison */}
          <div className="card-panel space-y-3">
            <div className="terminal-label">REPRODUCIBILITY METADATA</div>
            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs font-mono">
                <thead>
                  <tr className="border-b border-border text-text-3 text-[10px] uppercase">
                    <th className="pb-2">FIELD</th>
                    {compareData.runs.map((r) => (
                      <th key={r.id} className="pb-2 text-right pr-4">
                        {r.strategy_version_id}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody className="divide-y divide-border-subtle text-text-3 text-[11px]">
                  <tr>
                    <td className="py-2">GIT SHA</td>
                    {compareData.runs.map((r) => (
                      <td key={r.id} className="py-2 text-right pr-4 text-text-2">
                        {r.git_sha}
                      </td>
                    ))}
                  </tr>
                  <tr>
                    <td className="py-2">SPEC HASH</td>
                    {compareData.runs.map((r) => (
                      <td key={r.id} className="py-2 text-right pr-4 text-text-2">
                        {r.spec_hash}
                      </td>
                    ))}
                  </tr>
                  <tr>
                    <td className="py-2">COST MODEL</td>
                    {compareData.runs.map((r) => (
                      <td key={r.id} className="py-2 text-right pr-4 text-text-2">
                        {r.cost_model_hash}
                      </td>
                    ))}
                  </tr>
                  <tr>
                    <td className="py-2">DATA SNAPSHOT</td>
                    {compareData.runs.map((r) => (
                      <td key={r.id} className="py-2 text-right pr-4 text-text-2">
                        {r.data_snapshot_id}
                      </td>
                    ))}
                  </tr>
                  <tr>
                    <td className="py-2">RANDOM SEED</td>
                    {compareData.runs.map((r) => (
                      <td key={r.id} className="py-2 text-right pr-4 text-text-2">
                        {r.seed}
                      </td>
                    ))}
                  </tr>
                </tbody>
              </table>
            </div>
          </div>
        </>
      )}
    </div>
  );
}

export default function ComparePage() {
  return (
    <Suspense fallback={<div className="p-8 text-xs font-mono text-text-3">Loading comparison...</div>}>
      <CompareContent />
    </Suspense>
  );
}
