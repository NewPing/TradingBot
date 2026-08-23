"use client";

import { useEffect, useState } from "react";
import {
  FlaskConical,
  Play,
  Square,
  FastForward,
  Sparkles,
  ShieldCheck,
  ShieldAlert,
  CheckCircle2,
  XCircle,
  Clock,
  Cpu,
  Lock,
  Unlock,
  Layers,
  BarChart3,
  Scale,
  RefreshCw,
  Search,
  ExternalLink,
} from "lucide-react";
import { InfoTooltip } from "@/components/Tooltip";
import { MetricCard } from "@/components/MetricCard";
import { useTranslation } from "@/i18n";
import {
  fetchResearchStatus,
  startResearchDaemon,
  stopResearchDaemon,
  stepResearchDaemon,
  fetchResearchHypotheses,
  generateResearchHypothesis,
  fetchResearchSweeps,
  fetchResearchReports,
  fetchCandidateQueue,
  approveCandidate,
  rejectCandidate,
  unlockHoldoutPartition,
  ResearchDaemonStatusDTO,
  ResearchHypothesisDTO,
  ResearchSweepDTO,
  ResearchReportDTO,
} from "@/lib/api";

export default function ResearchPage() {
  const { t } = useTranslation();
  const [status, setStatus] = useState<ResearchDaemonStatusDTO | null>(null);
  const [hypotheses, setHypotheses] = useState<ResearchHypothesisDTO[]>([]);
  const [sweeps, setSweeps] = useState<ResearchSweepDTO[]>([]);
  const [reports, setReports] = useState<ResearchReportDTO[]>([]);
  const [candidateQueue, setCandidateQueue] = useState<ResearchReportDTO[]>([]);
  const [activeTab, setActiveTab] = useState<"queue" | "reports" | "hypotheses" | "gates">("queue");
  const [selectedReport, setSelectedReport] = useState<ResearchReportDTO | null>(null);
  const [loading, setLoading] = useState(true);
  const [actionLoading, setActionLoading] = useState(false);
  const [decisionNotes, setDecisionNotes] = useState("");

  // Modal states
  const [showGenModal, setShowGenModal] = useState(false);
  const [genFamily, setGenFamily] = useState("strategies/core_trend_v1.yaml");
  const [genType, setGenType] = useState("PARAM_REFINEMENT");
  const [genLayer, setGenLayer] = useState("l2");

  const [showHoldoutModal, setShowHoldoutModal] = useState(false);
  const [holdoutFamily, setHoldoutFamily] = useState("core_trend");
  const [holdoutUser, setHoldoutUser] = useState("operator");
  const [holdoutReason, setHoldoutReason] = useState("");

  const loadData = async () => {
    try {
      const [st, hyp, swp, reps, q] = await Promise.all([
        fetchResearchStatus().catch(() => null),
        fetchResearchHypotheses().catch(() => []),
        fetchResearchSweeps().catch(() => []),
        fetchResearchReports().catch(() => []),
        fetchCandidateQueue().catch(() => []),
      ]);
      if (st) setStatus(st);
      setHypotheses(hyp);
      setSweeps(swp);
      setReports(reps);
      setCandidateQueue(q);
      if (reps.length > 0 && !selectedReport) {
        setSelectedReport(reps[0]);
      }
    } catch (e) {
      console.error("Failed to load research data", e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
    const interval = setInterval(loadData, 5000);
    return () => clearInterval(interval);
  }, []);

  const handleToggleDaemon = async () => {
    setActionLoading(true);
    try {
      if (status?.running) {
        await stopResearchDaemon();
      } else {
        await startResearchDaemon();
      }
      await loadData();
    } catch (e) {
      console.error(e);
    } finally {
      setActionLoading(false);
    }
  };

  const handleStepCycle = async () => {
    setActionLoading(true);
    try {
      await stepResearchDaemon();
      await loadData();
    } catch (e) {
      console.error(e);
    } finally {
      setActionLoading(false);
    }
  };

  const handleGenerateHypothesis = async () => {
    setActionLoading(true);
    try {
      await generateResearchHypothesis(genFamily, genType, genLayer);
      setShowGenModal(false);
      await loadData();
    } catch (e) {
      console.error(e);
    } finally {
      setActionLoading(false);
    }
  };

  const handleApprove = async (reportId: string) => {
    setActionLoading(true);
    try {
      await approveCandidate(reportId, decisionNotes || "Approved based on clean 8-gate statistical pass.");
      setDecisionNotes("");
      await loadData();
    } catch (e) {
      console.error(e);
    } finally {
      setActionLoading(false);
    }
  };

  const handleReject = async (reportId: string) => {
    setActionLoading(true);
    try {
      await rejectCandidate(reportId, decisionNotes || "Manual rejection.");
      setDecisionNotes("");
      await loadData();
    } catch (e) {
      console.error(e);
    } finally {
      setActionLoading(false);
    }
  };

  const handleUnlockHoldout = async () => {
    if (!holdoutReason || holdoutReason.trim().length < 10) return;
    setActionLoading(true);
    try {
      await unlockHoldoutPartition(holdoutFamily, holdoutUser, holdoutReason);
      setShowHoldoutModal(false);
      setHoldoutReason("");
      await loadData();
    } catch (e) {
      console.error(e);
    } finally {
      setActionLoading(false);
    }
  };

  const totalTrials = status?.weekly_trial_budget.total_trials || 0;
  const trialsThisWeek = status?.weekly_trial_budget.trials_this_week || 0;
  const weeklyBudget = status?.weekly_trial_budget.weekly_budget || 500;
  const budgetPct = status?.weekly_trial_budget.budget_pct_used || 0;
  const deflatedPenalty = totalTrials > 1 ? (Math.sqrt(2 * Math.log(totalTrials)) * 0.2).toFixed(2) : "0.00";

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4 border-b border-border pb-4">
        <div>
          <div className="flex items-center gap-3">
            <h1 className="text-xl font-bold tracking-tight text-text-1 font-mono flex items-center gap-2">
              <FlaskConical className="w-5 h-5 text-pos" />
              {t("research.title")}
            </h1>
            <span className="text-[10px] px-2 py-0.5 rounded bg-pos/10 border border-pos/30 text-pos font-mono font-semibold">
              {t("research.discovery_loop_badge")}
            </span>
          </div>
          <p className="text-xs text-text-3 font-mono mt-1">
            {t("research.subtitle")}
          </p>
        </div>

        {/* Action Controls */}
        <div className="flex flex-wrap items-center gap-2">
          <button
            onClick={handleToggleDaemon}
            disabled={actionLoading}
            className={`flex items-center gap-2 px-3 py-1.5 rounded text-xs font-mono font-semibold border transition-all ${
              status?.running
                ? "bg-neg/10 border-neg/40 text-neg hover:bg-neg/20"
                : "bg-pos/10 border-pos/40 text-pos hover:bg-pos/20"
            }`}
            title="Toggle background automated hypothesis formulation and sweep loop"
          >
            {status?.running ? <Square className="w-3.5 h-3.5" /> : <Play className="w-3.5 h-3.5" />}
            {status?.running ? t("research.stop_daemon") : t("research.start_daemon")}
          </button>

          <button
            onClick={handleStepCycle}
            disabled={actionLoading}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded text-xs font-mono font-medium bg-surface border border-border text-text-2 hover:text-text-1 hover:border-text-3 transition-colors"
            title="Execute exactly one research iteration cycle immediately"
          >
            <FastForward className="w-3.5 h-3.5 text-info" />
            {t("research.step_cycle")}
          </button>

          <button
            onClick={() => setShowGenModal(true)}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded text-xs font-mono font-medium bg-surface border border-border text-text-2 hover:text-text-1 hover:border-text-3 transition-colors"
            title="Formulate a new strategy hypothesis across parameter, feature combo, or regime modalities"
          >
            <Sparkles className="w-3.5 h-3.5 text-warn" />
            {t("research.generate_hyp")}
          </button>

          <button
            onClick={() => setShowHoldoutModal(true)}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded text-xs font-mono font-medium bg-surface border border-border text-text-3 hover:text-warn transition-colors"
            title="Explicit human authorization to evaluate on the locked 2023–present holdout dataset"
          >
            <Lock className="w-3.5 h-3.5 text-warn" />
            {t("research.unlock_holdout_btn")}
          </button>
        </div>
      </div>

      {/* KPI Top Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
        <MetricCard
          label={t("research.daemon_status")}
          value={status?.running ? t("research.daemon_running") : t("research.daemon_idle")}
          subValue={`${status?.cycles_completed || 0} ${t("research.cycles_completed")} · ${status?.active_workers || 0} ${t("research.active_workers")}`}
          tooltip={t("tooltips.parity_desc")}
          tooltipTitle={t("research.daemon_status")}
          direction={status?.running ? "pos" : "neutral"}
        />

        <MetricCard
          label={t("research.weekly_trials")}
          value={`${trialsThisWeek} / ${weeklyBudget}`}
          subValue={`${budgetPct.toFixed(1)}% ${t("research.trials_consumed_sub")} (${totalTrials} lifetime)`}
          tooltip={t("tooltips.trial_budget_desc")}
          tooltipTitle={t("tooltips.trial_budget_title")}
          direction={budgetPct > 80 ? "neg" : "pos"}
        />

        <MetricCard
          label={t("research.deflated_penalty")}
          value={`+${deflatedPenalty} SR`}
          subValue={t("research.haircut_sub")}
          tooltip={t("tooltips.dsr_desc")}
          tooltipTitle={t("tooltips.dsr_title")}
          direction="neutral"
        />

        <MetricCard
          label={t("research.partition_isolation")}
          value={t("research.holdout_locked_val")}
          subValue={t("research.train_val_sub")}
          tooltip={t("tooltips.holdout_guard_desc")}
          tooltipTitle={t("tooltips.holdout_guard_title")}
          direction="pos"
        />
      </div>

      {/* Navigation Tabs */}
      <div className="flex border-b border-border text-xs font-mono">
        <button
          onClick={() => setActiveTab("queue")}
          className={`flex items-center gap-2 px-4 py-2.5 border-b-2 font-semibold transition-colors ${
            activeTab === "queue"
              ? "border-pos text-pos bg-surface"
              : "border-transparent text-text-3 hover:text-text-1"
          }`}
        >
          <ShieldCheck className="w-4 h-4" />
          {t("research.review_queue_title")}
          {candidateQueue.length > 0 && (
            <span className="px-1.5 py-0.2 rounded-full bg-pos text-bg text-[10px] font-bold">
              {candidateQueue.length}
            </span>
          )}
        </button>

        <button
          onClick={() => setActiveTab("reports")}
          className={`flex items-center gap-2 px-4 py-2.5 border-b-2 font-semibold transition-colors ${
            activeTab === "reports"
              ? "border-pos text-pos bg-surface"
              : "border-transparent text-text-3 hover:text-text-1"
          }`}
        >
          <BarChart3 className="w-4 h-4" />
          {t("research.reports_title")} ({reports.length})
        </button>

        <button
          onClick={() => setActiveTab("hypotheses")}
          className={`flex items-center gap-2 px-4 py-2.5 border-b-2 font-semibold transition-colors ${
            activeTab === "hypotheses"
              ? "border-pos text-pos bg-surface"
              : "border-transparent text-text-3 hover:text-text-1"
          }`}
        >
          <Layers className="w-4 h-4" />
          {t("research.hyp_queue_title")} ({hypotheses.length})
        </button>

        <button
          onClick={() => setActiveTab("gates")}
          className={`flex items-center gap-2 px-4 py-2.5 border-b-2 font-semibold transition-colors ${
            activeTab === "gates"
              ? "border-pos text-pos bg-surface"
              : "border-transparent text-text-3 hover:text-text-1"
          }`}
        >
          <Scale className="w-4 h-4" />
          {t("research.gatekeeper_matrix_title")}
        </button>
      </div>

      {/* TAB 1: Human Candidate Queue (Promotion Gate) */}
      {activeTab === "queue" && (
        <div className="space-y-4">
          <div className="p-3 bg-surface border border-border rounded text-xs font-mono flex items-center justify-between text-text-2">
            <div className="flex items-center gap-2">
              <ShieldCheck className="w-4 h-4 text-pos" />
              <span>
                <strong>{t("research.human_authority_title")}:</strong> {t("research.human_authority_desc")}
              </span>
            </div>
            <span className="text-[10px] text-text-3 font-mono">{t("research.human_authority_rule")}</span>
          </div>

          {candidateQueue.length === 0 ? (
            <div className="p-12 text-center bg-surface border border-border rounded">
              <ShieldCheck className="w-8 h-8 text-text-3 mx-auto mb-3" />
              <div className="text-sm font-mono text-text-2">{t("research.no_candidates_pending")}</div>
              <p className="text-xs text-text-3 font-mono mt-1">
                {t("research.no_candidates_desc")}
              </p>
            </div>
          ) : (
            <div className="space-y-4">
              {candidateQueue.map((c) => (
                <div key={c.id} className="p-4 bg-surface border border-border rounded space-y-4">
                  <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2 border-b border-border pb-3">
                    <div>
                      <div className="flex items-center gap-2">
                        <span className="text-sm font-bold font-mono text-text-1">{c.title}</span>
                        <span className="px-2 py-0.5 rounded bg-pos/10 border border-pos/30 text-pos text-[10px] font-mono font-semibold">
                          {t("research.gates_passed_8")}
                        </span>
                      </div>
                      <div className="text-xs text-text-3 font-mono mt-0.5">
                        {t("research.family_lbl")}: <span className="text-text-2 font-bold">{c.family}</span> · {t("research.spec_lbl")}: <span className="text-text-2">{c.strategy_spec_name}</span> · {t("research.hash_lbl")}: <span className="text-info">{c.spec_hash.substring(0, 10)}...</span>
                      </div>
                    </div>

                    <div className="flex items-center gap-2">
                      <button
                        onClick={() => handleApprove(c.id)}
                        disabled={actionLoading}
                        className="flex items-center gap-1.5 px-3 py-1.5 rounded bg-pos/20 border border-pos/50 text-pos hover:bg-pos/30 text-xs font-mono font-semibold transition-all"
                      >
                        <CheckCircle2 className="w-3.5 h-3.5" />
                        {t("research.approve_candidate")}
                      </button>

                      <button
                        onClick={() => handleReject(c.id)}
                        disabled={actionLoading}
                        className="flex items-center gap-1.5 px-3 py-1.5 rounded bg-neg/20 border border-neg/50 text-neg hover:bg-neg/30 text-xs font-mono font-semibold transition-all"
                      >
                        <XCircle className="w-3.5 h-3.5" />
                        {t("research.reject_candidate")}
                      </button>
                    </div>
                  </div>

                  {/* Side by side Train vs Val */}
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    <div className="p-3 bg-surface-2 border border-border rounded space-y-2">
                      <div className="text-xs font-mono font-bold text-text-2 flex items-center justify-between">
                        <span>{t("research.train_partition_header")}</span>
                        <span className="text-[10px] text-text-3">{t("research.in_sample_tag")}</span>
                      </div>
                      <div className="grid grid-cols-3 gap-2 text-xs font-mono">
                        <div>
                          <div className="text-[10px] text-text-3">Sharpe</div>
                          <div className="text-sm font-bold text-pos">{Number(c.train_metrics?.sharpe_ratio || 0).toFixed(2)}</div>
                        </div>
                        <div>
                          <div className="text-[10px] text-text-3">CAGR</div>
                          <div className="text-sm font-bold text-text-1">{(Number(c.train_metrics?.cagr || 0) * 100).toFixed(1)}%</div>
                        </div>
                        <div>
                          <div className="text-[10px] text-text-3">Max DD</div>
                          <div className="text-sm font-bold text-neg">{(Number(c.train_metrics?.max_drawdown || 0) * 100).toFixed(1)}%</div>
                        </div>
                      </div>
                    </div>

                    <div className="p-3 bg-surface-2 border border-border rounded space-y-2">
                      <div className="text-xs font-mono font-bold text-text-2 flex items-center justify-between">
                        <span>{t("research.val_partition_header")}</span>
                        <span className="text-[10px] text-pos font-semibold">{t("research.out_sample_tag")}</span>
                      </div>
                      <div className="grid grid-cols-3 gap-2 text-xs font-mono">
                        <div>
                          <div className="text-[10px] text-text-3">Sharpe</div>
                          <div className="text-sm font-bold text-pos">{Number(c.val_metrics?.sharpe_ratio || 0).toFixed(2)}</div>
                        </div>
                        <div>
                          <div className="text-[10px] text-text-3">CAGR</div>
                          <div className="text-sm font-bold text-text-1">{(Number(c.val_metrics?.cagr || 0) * 100).toFixed(1)}%</div>
                        </div>
                        <div>
                          <div className="text-[10px] text-text-3">Max DD</div>
                          <div className="text-sm font-bold text-neg">{(Number(c.val_metrics?.max_drawdown || 0) * 100).toFixed(1)}%</div>
                        </div>
                      </div>
                    </div>
                  </div>

                  {/* Notes input */}
                  <div className="flex items-center gap-2">
                    <input
                      type="text"
                      placeholder={t("research.decision_notes_placeholder")}
                      value={decisionNotes}
                      onChange={(e) => setDecisionNotes(e.target.value)}
                      className="flex-1 bg-surface-2 border border-border rounded px-3 py-1.5 text-xs font-mono text-text-1 focus:outline-none focus:border-pos"
                    />
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* TAB 2: Statistical Research Reports */}
      {activeTab === "reports" && (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
          {/* List column */}
          <div className="space-y-2">
            <div className="text-xs font-mono text-text-3 px-1">{t("research.generated_reports_lbl")}</div>
            {reports.length === 0 ? (
              <div className="p-6 bg-surface border border-border rounded text-center text-xs font-mono text-text-3">
                {t("research.no_reports_yet")}
              </div>
            ) : (
              reports.map((r) => {
                const isSelected = selectedReport?.id === r.id;
                return (
                  <div
                    key={r.id}
                    onClick={() => setSelectedReport(r)}
                    className={`p-3 rounded border cursor-pointer font-mono transition-all ${
                      isSelected
                        ? "bg-active border-pos border-l-4 text-text-1"
                        : "bg-surface border-border hover:bg-surface-2 text-text-2"
                    }`}
                  >
                    <div className="flex items-center justify-between text-xs font-bold mb-1">
                      <span className="truncate max-w-[200px]">{r.title}</span>
                      <span
                        className={`text-[10px] px-1.5 py-0.5 rounded font-semibold ${
                          r.gatekeeper_passed
                            ? "bg-pos/20 text-pos"
                            : "bg-neg/20 text-neg"
                        }`}
                      >
                        {r.gatekeeper_passed ? t("research.pass_badge_short") : t("research.reject_badge_short")}
                      </span>
                    </div>
                    <div className="text-[11px] text-text-3 flex items-center justify-between">
                      <span>{r.family}</span>
                      <span>{new Date(r.created_at).toLocaleDateString()}</span>
                    </div>
                  </div>
                );
              })
            )}
          </div>

          {/* Reader column */}
          <div className="lg:col-span-2 p-4 bg-surface border border-border rounded space-y-4">
            {selectedReport ? (
              <div className="space-y-4">
                <div className="border-b border-border pb-3 flex items-center justify-between">
                  <div>
                    <h2 className="text-sm font-bold font-mono text-text-1">{selectedReport.title}</h2>
                    <div className="text-xs text-text-3 font-mono mt-0.5">
                      {t("research.id_lbl")}: {selectedReport.id} · {t("research.verdict_lbl")}: <span className="font-bold text-pos">{selectedReport.verdict}</span>
                    </div>
                  </div>
                  <span
                    className={`px-2 py-0.5 rounded text-xs font-mono font-bold ${
                      selectedReport.gatekeeper_passed ? "bg-pos/20 text-pos border border-pos/40" : "bg-neg/20 text-neg border border-neg/40"
                    }`}
                  >
                    {selectedReport.gatekeeper_passed ? t("research.gatekeeper_passed_lbl") : `GATEKEEPER: ${selectedReport.verdict}`}
                  </span>
                </div>

                <div className="prose prose-invert max-w-none text-xs font-mono space-y-3 whitespace-pre-wrap leading-relaxed text-text-2">
                  {selectedReport.report_markdown}
                </div>
              </div>
            ) : (
              <div className="p-12 text-center text-xs font-mono text-text-3">
                {t("research.select_report_prompt")}
              </div>
            )}
          </div>
        </div>
      )}

      {/* TAB 3: Hypotheses & Sweeps */}
      {activeTab === "hypotheses" && (
        <div className="space-y-4">
          <div className="p-4 bg-surface border border-border rounded space-y-3">
            <div className="flex items-center justify-between">
              <div className="text-xs font-mono font-bold text-text-1">{t("research.modalities_5_title")}</div>
              <span className="text-[10px] text-pos font-mono font-semibold">{t("research.auto_generator_badge")}</span>
            </div>
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-2 text-xs font-mono">
              <div className="p-2.5 bg-surface-2 border border-border rounded">
                <div className="font-bold text-text-1 mb-1">{t("research.modality_1_title")}</div>
                <div className="text-[11px] text-text-3">{t("research.modality_1_desc")}</div>
              </div>
              <div className="p-2.5 bg-surface-2 border border-border rounded">
                <div className="font-bold text-text-1 mb-1">{t("research.modality_2_title")}</div>
                <div className="text-[11px] text-text-3">{t("research.modality_2_desc")}</div>
              </div>
              <div className="p-2.5 bg-surface-2 border border-border rounded">
                <div className="font-bold text-text-1 mb-1">{t("research.modality_3_title")}</div>
                <div className="text-[11px] text-text-3">{t("research.modality_3_desc")}</div>
              </div>
              <div className="p-2.5 bg-surface-2 border border-border rounded">
                <div className="font-bold text-text-1 mb-1">{t("research.modality_4_title")}</div>
                <div className="text-[11px] text-text-3">{t("research.modality_4_desc")}</div>
              </div>
            </div>
          </div>

          <div className="p-4 bg-surface border border-border rounded space-y-3">
            <div className="text-xs font-mono font-bold text-text-1">{t("research.hyp_ledger_title")}</div>
            <div className="overflow-x-auto">
              <table className="w-full text-xs font-mono">
                <thead>
                  <tr className="text-left text-text-3 border-b border-border">
                    <th className="pb-2">{t("research.col_id")}</th>
                    <th className="pb-2">{t("research.col_title")}</th>
                    <th className="pb-2">{t("research.col_generator")}</th>
                    <th className="pb-2">{t("research.col_family")}</th>
                    <th className="pb-2">{t("research.col_prior_score")}</th>
                    <th className="pb-2">{t("research.col_status")}</th>
                    <th className="pb-2">{t("research.col_created")}</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border">
                  {hypotheses.map((h) => (
                    <tr key={h.id} className="hover:bg-surface-2">
                      <td className="py-2 text-info">{h.id.substring(0, 10)}</td>
                      <td className="py-2 text-text-1 font-medium">{h.title}</td>
                      <td className="py-2 text-text-3">{h.generator_type}</td>
                      <td className="py-2 text-text-2">{h.family}</td>
                      <td className="py-2 text-pos font-bold">{h.prior_score.toFixed(2)}</td>
                      <td className="py-2">
                        <span
                          className={`px-1.5 py-0.5 rounded text-[10px] font-semibold ${
                            h.status === "VALIDATED" || h.status === "PROMOTED"
                              ? "bg-pos/20 text-pos"
                              : h.status === "REJECTED"
                              ? "bg-neg/20 text-neg"
                              : "bg-warn/20 text-warn"
                          }`}
                        >
                          {h.status}
                        </span>
                      </td>
                      <td className="py-2 text-text-3">{new Date(h.created_at).toLocaleTimeString()}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}

      {/* TAB 4: 8-Gate Statistical Gatekeeper Inspector */}
      {activeTab === "gates" && (
        <div className="space-y-4">
          <div className="p-4 bg-surface border border-border rounded space-y-3">
            <div className="text-xs font-mono font-bold text-text-1">
              {t("research.gatekeeper_8_rules_title")}
            </div>
            <p className="text-xs text-text-3 font-mono">
              {t("research.gatekeeper_8_rules_desc")}
            </p>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-3 pt-2">
              <div className="p-3 bg-surface-2 border border-border rounded space-y-1 font-mono text-xs">
                <div className="flex items-center justify-between text-text-1 font-bold">
                  <span>{t("research.gate_1_title")}</span>
                  <span className="text-pos text-[10px]">{t("research.gate_1_badge")}</span>
                </div>
                <p className="text-[11px] text-text-3">
                  {t("research.gate_1_desc")}
                </p>
              </div>

              <div className="p-3 bg-surface-2 border border-border rounded space-y-1 font-mono text-xs">
                <div className="flex items-center justify-between text-text-1 font-bold">
                  <span>{t("research.gate_2_title")}</span>
                  <span className="text-pos text-[10px]">{t("research.gate_2_badge")}</span>
                </div>
                <p className="text-[11px] text-text-3">
                  {t("research.gate_2_desc")}
                </p>
              </div>

              <div className="p-3 bg-surface-2 border border-border rounded space-y-1 font-mono text-xs">
                <div className="flex items-center justify-between text-text-1 font-bold">
                  <span>{t("research.gate_3_title")}</span>
                  <span className="text-pos text-[10px]">{t("research.gate_3_badge")}</span>
                </div>
                <p className="text-[11px] text-text-3">
                  {t("research.gate_3_desc")}
                </p>
              </div>

              <div className="p-3 bg-surface-2 border border-border rounded space-y-1 font-mono text-xs">
                <div className="flex items-center justify-between text-text-1 font-bold">
                  <span>{t("research.gate_4_title")}</span>
                  <span className="text-pos text-[10px]">{t("research.gate_4_badge")}</span>
                </div>
                <p className="text-[11px] text-text-3">
                  {t("research.gate_4_desc")}
                </p>
              </div>

              <div className="p-3 bg-surface-2 border border-border rounded space-y-1 font-mono text-xs">
                <div className="flex items-center justify-between text-text-1 font-bold">
                  <span>{t("research.gate_5_title")}</span>
                  <span className="text-pos text-[10px]">{t("research.gate_5_badge")}</span>
                </div>
                <p className="text-[11px] text-text-3">
                  {t("research.gate_5_desc")}
                </p>
              </div>

              <div className="p-3 bg-surface-2 border border-border rounded space-y-1 font-mono text-xs">
                <div className="flex items-center justify-between text-text-1 font-bold">
                  <span>{t("research.gate_6_title")}</span>
                  <span className="text-pos text-[10px]">{t("research.gate_6_badge")}</span>
                </div>
                <p className="text-[11px] text-text-3">
                  {t("research.gate_6_desc")}
                </p>
              </div>

              <div className="p-3 bg-surface-2 border border-border rounded space-y-1 font-mono text-xs">
                <div className="flex items-center justify-between text-text-1 font-bold">
                  <span>{t("research.gate_7_title")}</span>
                  <span className="text-pos text-[10px]">{t("research.gate_7_badge")}</span>
                </div>
                <p className="text-[11px] text-text-3">
                  {t("research.gate_7_desc")}
                </p>
              </div>

              <div className="p-3 bg-surface-2 border border-border rounded space-y-1 font-mono text-xs">
                <div className="flex items-center justify-between text-text-1 font-bold">
                  <span>{t("research.gate_8_title")}</span>
                  <span className="text-pos text-[10px]">{t("research.gate_8_badge")}</span>
                </div>
                <p className="text-[11px] text-text-3">
                  {t("research.gate_8_desc")}
                </p>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* MODAL: Generate Hypothesis */}
      {showGenModal && (
        <div className="fixed inset-0 bg-black/70 flex items-center justify-center z-50 p-4">
          <div className="bg-surface border border-border rounded-lg max-w-md w-full p-5 space-y-4 font-mono">
            <div className="flex items-center justify-between border-b border-border pb-2">
              <div className="text-sm font-bold text-text-1 flex items-center gap-2">
                <Sparkles className="w-4 h-4 text-pos" />
                {t("research.modal_gen_title")}
              </div>
              <button
                onClick={() => setShowGenModal(false)}
                className="text-text-3 hover:text-text-1 text-sm"
              >
                ✕
              </button>
            </div>

            <div className="space-y-3 text-xs">
              <div>
                <label className="block text-text-3 mb-1">{t("research.modal_gen_base_spec")}</label>
                <select
                  value={genFamily}
                  onChange={(e) => setGenFamily(e.target.value)}
                  className="w-full bg-surface-2 border border-border rounded p-2 text-text-1"
                >
                  <option value="strategies/core_trend_v1.yaml">core_trend_v1.yaml (CORE)</option>
                  <option value="strategies/swing_meanrev_v1.yaml">swing_meanrev_v1.yaml (SWING)</option>
                  <option value="strategies/core_narrative_l4.yaml">core_narrative_l4.yaml (L4)</option>
                </select>
              </div>

              <div>
                <label className="block text-text-3 mb-1">{t("research.modal_gen_modality")}</label>
                <select
                  value={genType}
                  onChange={(e) => setGenType(e.target.value)}
                  className="w-full bg-surface-2 border border-border rounded p-2 text-text-1"
                >
                  <option value="PARAM_REFINEMENT">{t("research.generator_param")} (±20% Jitter)</option>
                  <option value="FEATURE_COMBO">{t("research.generator_feature")} (L2/L3/L4)</option>
                  <option value="REGIME_VARIANT">{t("research.generator_regime")} (4-Quadrant)</option>
                </select>
              </div>

              {genType === "FEATURE_COMBO" && (
                <div>
                  <label className="block text-text-3 mb-1">{t("research.modal_gen_layer")}</label>
                  <select
                    value={genLayer}
                    onChange={(e) => setGenLayer(e.target.value)}
                    className="w-full bg-surface-2 border border-border rounded p-2 text-text-1"
                  >
                    <option value="l2">L2: Statistical & Volatility</option>
                    <option value="l3">L3: GARP Fundamental Valuation</option>
                    <option value="l4">L4: Narrative & LLM Sentiment</option>
                  </select>
                </div>
              )}
            </div>

            <div className="flex justify-end gap-2 pt-2 border-t border-border">
              <button
                onClick={() => setShowGenModal(false)}
                className="px-3 py-1.5 rounded border border-border text-xs text-text-3 hover:text-text-1"
              >
                {t("common.cancel")}
              </button>
              <button
                onClick={handleGenerateHypothesis}
                disabled={actionLoading}
                className="px-3 py-1.5 rounded bg-pos text-bg text-xs font-bold hover:bg-pos/90"
              >
                {actionLoading ? t("research.modal_gen_submitting") : t("research.modal_gen_submit")}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* MODAL: Unlock Holdout */}
      {showHoldoutModal && (
        <div className="fixed inset-0 bg-black/70 flex items-center justify-center z-50 p-4">
          <div className="bg-surface border border-border rounded-lg max-w-md w-full p-5 space-y-4 font-mono">
            <div className="flex items-center justify-between border-b border-border pb-2">
              <div className="text-sm font-bold text-warn flex items-center gap-2">
                <Lock className="w-4 h-4 text-warn" />
                {t("research.modal_holdout_title")}
              </div>
              <button
                onClick={() => setShowHoldoutModal(false)}
                className="text-text-3 hover:text-text-1 text-sm"
              >
                ✕
              </button>
            </div>

            <div className="p-2.5 bg-warn/10 border border-warn/30 rounded text-xs text-warn">
              <strong>{t("research.modal_holdout_warn_title")}:</strong> {t("research.modal_holdout_warn_desc")}
            </div>

            <div className="space-y-3 text-xs">
              <div>
                <label className="block text-text-3 mb-1">{t("research.modal_holdout_family")}</label>
                <input
                  type="text"
                  value={holdoutFamily}
                  onChange={(e) => setHoldoutFamily(e.target.value)}
                  className="w-full bg-surface-2 border border-border rounded p-2 text-text-1"
                />
              </div>

              <div>
                <label className="block text-text-3 mb-1">{t("research.modal_holdout_user")}</label>
                <input
                  type="text"
                  value={holdoutUser}
                  onChange={(e) => setHoldoutUser(e.target.value)}
                  className="w-full bg-surface-2 border border-border rounded p-2 text-text-1"
                />
              </div>

              <div>
                <label className="block text-text-3 mb-1">{t("research.modal_holdout_reason")}</label>
                <textarea
                  rows={3}
                  value={holdoutReason}
                  onChange={(e) => setHoldoutReason(e.target.value)}
                  placeholder={t("research.modal_holdout_reason_placeholder")}
                  className="w-full bg-surface-2 border border-border rounded p-2 text-text-1"
                />
              </div>
            </div>

            <div className="flex justify-end gap-2 pt-2 border-t border-border">
              <button
                onClick={() => setShowHoldoutModal(false)}
                className="px-3 py-1.5 rounded border border-border text-xs text-text-3 hover:text-text-1"
              >
                {t("common.cancel")}
              </button>
              <button
                onClick={handleUnlockHoldout}
                disabled={actionLoading || holdoutReason.trim().length < 10}
                className="px-3 py-1.5 rounded bg-warn text-bg text-xs font-bold hover:bg-warn/90 disabled:opacity-50"
              >
                {actionLoading ? t("research.modal_holdout_submitting") : t("research.modal_holdout_submit")}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
