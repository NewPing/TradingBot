"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { api, LineageResponse, StrategyVersion } from "@/lib/api";
import { InfoTooltip } from "@/components/Tooltip";
import {
  Layers,
  GitBranch,
  GitCompare,
  RefreshCw,
  Eye,
  CheckSquare,
  Square,
  ChevronRight,
  ShieldAlert,
} from "lucide-react";

export default function VersionsPage() {
  const router = useRouter();
  const [versions, setVersions] = useState<StrategyVersion[]>([]);
  const [selectedFamily, setSelectedFamily] = useState<string>("ALL");
  const [selectedVersions, setSelectedVersions] = useState<string[]>([]);
  const [activeLineage, setActiveLineage] = useState<LineageResponse | null>(null);
  const [loading, setLoading] = useState(true);

  const fetchVersions = async () => {
    setLoading(true);
    const data = await api.getVersions(selectedFamily === "ALL" ? undefined : selectedFamily);
    setVersions(data);
    setLoading(false);
  };

  useEffect(() => {
    fetchVersions();
  }, [selectedFamily]);

  const families = ["ALL", ...Array.from(new Set(versions.map((v) => v.family)))];

  const handleToggleSelect = (id: string) => {
    setSelectedVersions((prev) =>
      prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id]
    );
  };

  const handleShowLineage = async (id: string) => {
    const lineage = await api.getLineage(id);
    setActiveLineage(lineage);
  };

  const handleCompareSelected = async () => {
    if (selectedVersions.length === 0) return;
    // Find latest run for each selected version
    const allRuns = await api.getRuns(undefined, 100);
    const runIds: string[] = [];
    for (const vId of selectedVersions) {
      const match = allRuns.find((r) => r.strategy_version_id === vId);
      if (match) runIds.push(match.id);
    }
    if (runIds.length > 0) {
      router.push(`/compare?run_ids=${runIds.join(",")}`);
    } else {
      alert("No backtest runs found for selected versions. Please run backtests first.");
    }
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-border pb-5">
        <div>
          <h1 className="text-xl font-bold font-mono tracking-tight text-text-1">
            STRATEGY VERSION REGISTRY
          </h1>
          <p className="text-xs text-text-2 font-mono mt-1">
            Immutable specifications, SHA-256 cryptographic signatures, and ancestral lineage trees.
          </p>
        </div>
        <div className="flex items-center gap-2">
          {selectedVersions.length >= 2 && (
            <button onClick={handleCompareSelected} className="btn-primary">
              <GitCompare className="w-3.5 h-3.5" />
              <span>COMPARE ({selectedVersions.length})</span>
            </button>
          )}
          <button
            onClick={async () => {
              await api.syncStrategies();
              await fetchVersions();
            }}
            className="btn-terminal"
          >
            <RefreshCw className="w-3.5 h-3.5" />
            <span>SYNC YAML</span>
          </button>
        </div>
      </div>

      {/* Family Filter Tabs */}
      <div className="flex items-center gap-1.5 overflow-x-auto pb-2">
        {families.map((fam) => (
          <button
            key={fam}
            onClick={() => setSelectedFamily(fam)}
            className={`px-3 py-1 rounded text-xs font-mono transition-all ${
              selectedFamily === fam
                ? "bg-surface-2 text-pos border border-border font-semibold"
                : "text-text-3 hover:text-text-1 hover:bg-surface border border-transparent"
            }`}
          >
            {fam}
          </button>
        ))}
      </div>

      {/* Versions Table */}
      <div className="card-panel">
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs font-mono">
            <thead>
              <tr className="border-b border-border text-text-3 text-[10px] uppercase">
                <th className="pb-3 pl-2 w-8"></th>
                <th className="pb-3">
                  <span className="inline-flex items-center">
                    VERSION ID
                    <InfoTooltip
                      title="Strategy Version ID"
                      content="Unique family identifier combined with semantic versioning (e.g. core_trend_1.0.0)."
                    />
                  </span>
                </th>
                <th className="pb-3">FAMILY</th>
                <th className="pb-3">
                  <span className="inline-flex items-center">
                    STATUS
                    <InfoTooltip
                      title="Promotion Stage"
                      content="RESEARCH (Fitting) -> CANDIDATE (Passed statistical gates) -> PAPER (90-day forward test) -> SHADOW ($0 live order comparison) -> LIVE (Real money)."
                    />
                  </span>
                </th>
                <th className="pb-3">
                  <span className="inline-flex items-center">
                    PARENT LINEAGE
                    <InfoTooltip
                      title="Ancestral Lineage"
                      content="The parent strategy version this version was derived or tuned from."
                    />
                  </span>
                </th>
                <th className="pb-3">
                  <span className="inline-flex items-center">
                    SPEC HASH
                    <InfoTooltip
                      title="SHA-256 Spec Hash"
                      content="Cryptographic signature of the exact YAML parameters. If parameters change, the hash changes and immutability rules prevent silent overwriting."
                    />
                  </span>
                </th>
                <th className="pb-3">CREATED</th>
                <th className="pb-3 text-right pr-2">ACTIONS</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border-subtle">
              {versions.length === 0 ? (
                <tr>
                  <td colSpan={8} className="py-8 text-center text-text-3">
                    {loading
                      ? "Loading version registry..."
                      : "No strategy versions registered for this filter."}
                  </td>
                </tr>
              ) : (
                versions.map((v) => {
                  const isSelected = selectedVersions.includes(v.id);
                  return (
                    <tr
                      key={v.id}
                      className={`hover:bg-surface-2 transition-colors ${
                        isSelected ? "bg-active" : ""
                      }`}
                    >
                      <td className="py-3 pl-2">
                        <button
                          onClick={() => handleToggleSelect(v.id)}
                          className="text-text-3 hover:text-pos"
                        >
                          {isSelected ? (
                            <CheckSquare className="w-4 h-4 text-pos" />
                          ) : (
                            <Square className="w-4 h-4" />
                          )}
                        </button>
                      </td>
                      <td className="py-3 font-semibold text-text-1">{v.id}</td>
                      <td className="py-3 text-text-2">{v.family}</td>
                      <td className="py-3">
                        <span className="terminal-badge bg-surface-2 border-border text-pos">
                          {v.status}
                        </span>
                      </td>
                      <td className="py-3 text-text-3">
                        {v.parent_id ? (
                          <span className="text-text-2 flex items-center gap-1">
                            <GitBranch className="w-3 h-3 text-text-3" />
                            {v.parent_id}
                          </span>
                        ) : (
                          "— (Root)"
                        )}
                      </td>
                      <td className="py-3 text-text-3 text-[11px]">
                        <span title={v.spec_hash}>{v.spec_hash.substring(0, 8)}...</span>
                      </td>
                      <td className="py-3 text-text-3 text-[11px]">
                        {new Date(v.created_at).toLocaleDateString()}
                      </td>
                      <td className="py-3 text-right pr-2">
                        <button
                          onClick={() => handleShowLineage(v.id)}
                          className="btn-terminal py-1 px-2 text-[11px]"
                        >
                          <GitBranch className="w-3 h-3" />
                          <span>LINEAGE</span>
                        </button>
                      </td>
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* Lineage Modal / Inspector */}
      {activeLineage && (
        <div className="card-panel border-l-4 border-l-pos space-y-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <GitBranch className="w-4 h-4 text-pos" />
              <span className="text-xs font-mono font-semibold text-text-1">
                LINEAGE TREE: {activeLineage.current.id}
              </span>
            </div>
            <button
              onClick={() => setActiveLineage(null)}
              className="text-xs font-mono text-text-3 hover:text-text-1"
            >
              ✕ CLOSE
            </button>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-4 pt-2">
            {/* Ancestors */}
            <div className="bg-surface-2 border border-border rounded p-3 space-y-2">
              <div className="terminal-label">ANCESTORS (PARENTS)</div>
              {activeLineage.ancestors.length === 0 ? (
                <div className="text-xs font-mono text-text-3">Root specification (No parent).</div>
              ) : (
                <div className="space-y-1.5">
                  {activeLineage.ancestors.map((anc) => (
                    <div
                      key={anc.id}
                      className="text-xs font-mono text-text-2 flex items-center gap-1.5"
                    >
                      <ChevronRight className="w-3 h-3 text-text-3" />
                      <span>{anc.id}</span>
                      <span className="text-[10px] text-text-3">({anc.status})</span>
                    </div>
                  ))}
                </div>
              )}
            </div>

            {/* Current Target */}
            <div className="bg-active border border-pos rounded p-3 space-y-2">
              <div className="terminal-label text-pos">CURRENT VERSION</div>
              <div className="text-xs font-mono font-bold text-text-1">
                {activeLineage.current.id}
              </div>
              <div className="text-[11px] font-mono text-text-3">
                Spec Hash: {activeLineage.current.spec_hash.substring(0, 12)}...
              </div>
              <span className="terminal-badge bg-surface border-border text-pos">
                {activeLineage.current.status}
              </span>
            </div>

            {/* Direct Children */}
            <div className="bg-surface-2 border border-border rounded p-3 space-y-2">
              <div className="terminal-label">CHILDREN / VARIANTS</div>
              {activeLineage.children.length === 0 ? (
                <div className="text-xs font-mono text-text-3">
                  No derived versions branched from this spec yet.
                </div>
              ) : (
                <div className="space-y-1.5">
                  {activeLineage.children.map((child) => (
                    <div
                      key={child.id}
                      className="text-xs font-mono text-text-2 flex items-center gap-1.5"
                    >
                      <ChevronRight className="w-3 h-3 text-pos" />
                      <span>{child.id}</span>
                      <span className="text-[10px] text-text-3">({child.status})</span>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
