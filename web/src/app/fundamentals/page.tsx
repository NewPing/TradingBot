"use client";

import { useEffect, useState } from "react";
import {
  FileSpreadsheet,
  RefreshCw,
  ShieldAlert,
  ShieldCheck,
  TrendingUp,
  Percent,
  CheckCircle2,
  Calendar,
  Layers,
  Scale,
  Award,
} from "lucide-react";
import { InfoTooltip } from "@/components/Tooltip";
import { MetricCard } from "@/components/MetricCard";
import { useTranslation } from "@/i18n";
import {
  api,
  FundamentalSnapshot,
  EarningsEvent,
  FundamentalScreenerItem,
} from "@/lib/api";

export default function FundamentalsPage() {
  const { t } = useTranslation();
  const [selectedSymbol, setSelectedSymbol] = useState<string>("AAPL");
  const [snapshot, setSnapshot] = useState<FundamentalSnapshot | null>(null);
  const [earnings, setEarnings] = useState<EarningsEvent[]>([]);
  const [screener, setScreener] = useState<FundamentalScreenerItem[]>([]);
  const [loading, setLoading] = useState<boolean>(true);

  const loadData = async () => {
    setLoading(true);
    try {
      const [snap, cal, scr] = await Promise.all([
        api.getSymbolFundamentals(selectedSymbol),
        api.getEarningsCalendar(2),
        api.getFundamentalScreener(),
      ]);
      setSnapshot(snap);
      setEarnings(cal);
      if (scr) {
        setScreener(scr.items);
      }
    } catch (err) {
      console.error("Error fetching fundamentals data:", err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, [selectedSymbol]);

  const activeBlackoutsCount = earnings.filter(
    (e) => e.blackout_status === "BLACKOUT_ACTIVE"
  ).length;

  return (
    <div className="space-y-6">
      {/* Page Header */}
      <div className="flex items-center justify-between border-b border-border pb-4">
        <div>
          <div className="flex items-center gap-2">
            <h1 className="text-xl font-bold tracking-tight text-text-1 font-mono">
              {t("fundamentals.title")}
            </h1>
            <span className="px-2 py-0.5 rounded text-[10px] font-mono font-bold bg-pos/10 border border-pos/30 text-pos">
              L3
            </span>
            <span className="px-2 py-0.5 rounded text-[10px] font-mono font-bold bg-surface border border-border text-text-2 flex items-center gap-1">
              <span>{t("fundamentals.point_in_time_badge")}</span>
              <InfoTooltip
                title={t("tooltips.pit_filings_title")}
                content={t("tooltips.pit_filings_desc")}
              />
            </span>
          </div>
          <p className="text-xs text-text-3 font-mono mt-1">
            {t("fundamentals.subtitle")}
          </p>
        </div>

        <div className="flex items-center gap-3">
          <button
            onClick={loadData}
            disabled={loading}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded bg-surface hover:bg-surface-2 border border-border text-text-2 hover:text-text-1 text-xs font-mono transition-colors disabled:opacity-50"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${loading ? "animate-spin" : ""}`} />
            <span>{t("common.refresh")}</span>
          </button>
        </div>
      </div>

      {/* Overview Top Metric Cards */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <MetricCard
          label={t("fundamentals.avg_roic_label")}
          value={`${snapshot ? (snapshot.roic * 100).toFixed(1) : "35.2"}%`}
          subValue={t("fundamentals.avg_roic_sub")}
          direction="pos"
          tooltipTitle={t("tooltips.roic_title")}
          tooltip={t("tooltips.roic_desc")}
        />
        <MetricCard
          label={t("fundamentals.sloan_ratio_label")}
          value={snapshot ? snapshot.sloan_accrual.toFixed(3) : "-0.018"}
          subValue={t("fundamentals.sloan_ratio_sub")}
          direction={snapshot && snapshot.sloan_accrual < 0.05 ? "pos" : "neutral"}
          tooltipTitle={t("tooltips.sloan_accrual_title")}
          tooltip={t("tooltips.sloan_accrual_desc")}
        />
        <MetricCard
          label={t("fundamentals.ev_ebitda_label")}
          value={snapshot ? `${snapshot.ev_ebitda.toFixed(1)}x` : "22.1x"}
          subValue={t("fundamentals.ev_ebitda_sub")}
          tooltipTitle={t("tooltips.ev_ebitda_title")}
          tooltip={t("tooltips.ev_ebitda_desc")}
        />
        <MetricCard
          label={t("fundamentals.earnings_blackouts_label")}
          value={activeBlackoutsCount}
          subValue={t("fundamentals.earnings_blackouts_sub")}
          direction={activeBlackoutsCount > 0 ? "neg" : "pos"}
          tooltipTitle={t("tooltips.blackout_guard_title")}
          tooltip={t("tooltips.blackout_guard_desc")}
        />
      </div>

      {/* Selected Company Quality & Valuation Deep Dive */}
      <div className="bg-surface border border-border rounded-lg p-5 space-y-5">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-border pb-4">
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 rounded bg-surface-2 border border-border flex items-center justify-center text-pos">
              <Award className="w-5 h-5" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <span className="text-base font-bold font-mono text-text-1">
                  {snapshot?.symbol || selectedSymbol}
                </span>
                <span className="text-xs text-text-3 font-mono">
                  {snapshot ? `${t("fundamentals.filing_period_lbl")}: ${snapshot.period}` : ""}
                </span>
              </div>
              <div className="text-[11px] text-text-3 font-mono">
                {snapshot ? `${t("fundamentals.report_date_lbl")}: ${snapshot.report_date} · ${t("fundamentals.sec_filing_date_lbl")}: ${snapshot.filing_date.substring(0, 10)}` : ""}
              </div>
            </div>
          </div>

          {/* Symbol Selector Pills */}
          <div className="flex items-center gap-1.5 flex-wrap">
            {["AAPL", "MSFT", "NVDA", "GOOGL", "AMZN", "JPM"].map((sym) => (
              <button
                key={sym}
                onClick={() => setSelectedSymbol(sym)}
                className={`px-3 py-1 rounded text-xs font-mono font-semibold transition-all ${
                  selectedSymbol === sym
                    ? "bg-pos text-black shadow-sm"
                    : "bg-surface-2 hover:bg-active text-text-2 border border-border"
                }`}
              >
                {sym}
              </button>
            ))}
          </div>
        </div>

        {/* Score Breakdown Cards */}
        {snapshot && (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            {/* Quality Scorecard */}
            <div className="bg-surface-2 border border-border rounded p-4 space-y-4">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <span className="text-xs font-mono font-bold uppercase text-text-1">
                    {t("fundamentals.quality_scorecard_title")}
                  </span>
                  <InfoTooltip
                    title={t("tooltips.garp_title")}
                    content={t("tooltips.garp_desc")}
                  />
                </div>
                <div className="text-right">
                  <span className="text-lg font-mono font-bold text-pos">
                    {(snapshot.quality_score * 100).toFixed(0)}
                  </span>
                  <span className="text-xs font-mono text-text-3"> / 100</span>
                </div>
              </div>

              {/* Progress Bar */}
              <div className="w-full bg-surface rounded-full h-2 overflow-hidden border border-border">
                <div
                  className="bg-pos h-full transition-all duration-500 rounded-full"
                  style={{ width: `${Math.min(100, Math.max(0, snapshot.quality_score * 100))}%` }}
                />
              </div>

              {/* Quality Sub-metrics */}
              <div className="grid grid-cols-2 gap-3 pt-2 text-xs font-mono">
                <div className="bg-surface border border-border rounded p-2.5">
                  <div className="text-text-3 text-[10px]">{t("fundamentals.roic_label")}</div>
                  <div className="text-text-1 font-bold">{(snapshot.roic * 100).toFixed(1)}%</div>
                </div>
                <div className="bg-surface border border-border rounded p-2.5">
                  <div className="text-text-3 text-[10px]">{t("fundamentals.sloan_accruals")}</div>
                  <div className="text-text-1 font-bold">{snapshot.sloan_accrual.toFixed(3)}</div>
                </div>
                <div className="bg-surface border border-border rounded p-2.5">
                  <div className="text-text-3 text-[10px]">{t("fundamentals.operating_margin_lbl")}</div>
                  <div className="text-text-1 font-bold">{(snapshot.operating_margin * 100).toFixed(1)}%</div>
                </div>
                <div className="bg-surface border border-border rounded p-2.5">
                  <div className="text-text-3 text-[10px]">{t("fundamentals.gross_margin_lbl")}</div>
                  <div className="text-text-1 font-bold">{(snapshot.gross_margin * 100).toFixed(1)}%</div>
                </div>
              </div>
            </div>

            {/* Valuation Scorecard */}
            <div className="bg-surface-2 border border-border rounded p-4 space-y-4">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <span className="text-xs font-mono font-bold uppercase text-text-1">
                    {t("fundamentals.valuation_scorecard_title")}
                  </span>
                  <InfoTooltip
                    title={t("tooltips.ev_ebitda_title")}
                    content={t("tooltips.ev_ebitda_desc")}
                  />
                </div>
                <div className="text-right">
                  <span className="text-lg font-mono font-bold text-info">
                    {(snapshot.value_score * 100).toFixed(0)}
                  </span>
                  <span className="text-xs font-mono text-text-3"> / 100</span>
                </div>
              </div>

              {/* Progress Bar */}
              <div className="w-full bg-surface rounded-full h-2 overflow-hidden border border-border">
                <div
                  className="bg-info h-full transition-all duration-500 rounded-full"
                  style={{ width: `${Math.min(100, Math.max(0, snapshot.value_score * 100))}%` }}
                />
              </div>

              {/* Valuation Sub-metrics */}
              <div className="grid grid-cols-2 gap-3 pt-2 text-xs font-mono">
                <div className="bg-surface border border-border rounded p-2.5">
                  <div className="text-text-3 text-[10px]">{t("tooltips.ev_ebitda_title")}</div>
                  <div className="text-text-1 font-bold">{snapshot.ev_ebitda.toFixed(1)}x</div>
                </div>
                <div className="bg-surface border border-border rounded p-2.5">
                  <div className="text-text-3 text-[10px]">{t("fundamentals.pe_ratio_lbl")}</div>
                  <div className="text-text-1 font-bold">{snapshot.pe_ratio.toFixed(1)}x</div>
                </div>
                <div className="bg-surface border border-border rounded p-2.5">
                  <div className="text-text-3 text-[10px]">{t("fundamentals.fcf_yield_label")}</div>
                  <div className="text-text-1 font-bold">{(snapshot.fcf_yield * 100).toFixed(1)}%</div>
                </div>
                <div className="bg-surface border border-border rounded p-2.5">
                  <div className="text-text-3 text-[10px]">{t("fundamentals.debt_equity_lbl")}</div>
                  <div className="text-text-1 font-bold">{snapshot.debt_to_equity.toFixed(2)}</div>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* Engine Rationale Banner */}
        {snapshot?.rationale && (
          <div className="p-3 bg-surface-2 border border-border rounded text-xs font-mono text-text-2 flex items-start gap-2">
            <CheckCircle2 className="w-4 h-4 text-pos shrink-0 mt-0.5" />
            <div>
              <span className="text-text-1 font-bold">{t("fundamentals.alpha_rationale_lbl")}: </span>
              {snapshot.rationale}
            </div>
          </div>
        )}
      </div>

      {/* Two Column Layout: Earnings Blackout Calendar & Universe Screener */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Earnings Calendar & Blackout Blotter */}
        <div className="bg-surface border border-border rounded-lg p-5 space-y-4">
          <div className="flex items-center justify-between border-b border-border pb-3">
            <div className="flex items-center gap-2">
              <Calendar className="w-4 h-4 text-pos" />
              <h2 className="text-xs font-mono font-bold uppercase text-text-1">
                {t("fundamentals.earnings_calendar_title")}
              </h2>
              <InfoTooltip
                title={t("tooltips.blackout_guard_title")}
                content={t("tooltips.blackout_guard_desc")}
              />
            </div>
            <span className="text-[11px] font-mono text-text-3">
              {earnings.length} {t("fundamentals.scheduled_events_count")}
            </span>
          </div>

          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs font-mono">
              <thead>
                <tr className="border-b border-border text-text-3 text-[10px] uppercase">
                  <th className="pb-2">{t("common.symbol")}</th>
                  <th className="pb-2">{t("common.date")}</th>
                  <th className="pb-2">{t("fundamentals.timing_col")}</th>
                  <th className="pb-2">{t("fundamentals.period_col")}</th>
                  <th className="pb-2">{t("fundamentals.est_eps_col")}</th>
                  <th className="pb-2 text-right">{t("common.status")}</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border/40">
                {earnings.map((ev) => (
                  <tr key={ev.symbol} className="hover:bg-surface-2/60 transition-colors">
                    <td className="py-2.5 font-bold text-text-1">{ev.symbol}</td>
                    <td className="py-2.5 text-text-2">{ev.event_date}</td>
                    <td className="py-2.5 text-text-3">{ev.time_of_day}</td>
                    <td className="py-2.5 text-text-3">{ev.fiscal_period || "—"}</td>
                    <td className="py-2.5 text-text-2">
                      {ev.eps_estimated !== null && ev.eps_estimated !== undefined
                        ? `$${ev.eps_estimated.toFixed(2)}`
                        : "—"}
                    </td>
                    <td className="py-2.5 text-right">
                      {ev.blackout_status === "BLACKOUT_ACTIVE" ? (
                        <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-bold bg-neg/10 border border-neg/30 text-neg">
                          <ShieldAlert className="w-3 h-3" />
                          {t("fundamentals.blackout_badge")} ({ev.days_until_event}d)
                        </span>
                      ) : (
                        <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-bold bg-pos/10 border border-pos/30 text-pos">
                          <ShieldCheck className="w-3 h-3" />
                          {t("fundamentals.safe_badge")} ({ev.days_until_event}d)
                        </span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

        {/* Cross-Sectional Universe Screener */}
        <div className="bg-surface border border-border rounded-lg p-5 space-y-4">
          <div className="flex items-center justify-between border-b border-border pb-3">
            <div className="flex items-center gap-2">
              <Scale className="w-4 h-4 text-pos" />
              <h2 className="text-xs font-mono font-bold uppercase text-text-1">
                {t("fundamentals.screener_title")}
              </h2>
              <InfoTooltip
                title={t("fundamentals.screener_title")}
                content={t("fundamentals.screener_desc")}
              />
            </div>
            <span className="text-[11px] font-mono text-text-3">
              {screener.length} {t("fundamentals.universe_equities_count")}
            </span>
          </div>

          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs font-mono">
              <thead>
                <tr className="border-b border-border text-text-3 text-[10px] uppercase">
                  <th className="pb-2">{t("common.symbol")}</th>
                  <th className="pb-2">{t("fundamentals.sector_col")}</th>
                  <th className="pb-2">
                    <span className="inline-flex items-center">
                      {t("fundamentals.quality_col")}
                      <InfoTooltip title={t("tooltips.garp_title")} content={t("tooltips.garp_desc")} />
                    </span>
                  </th>
                  <th className="pb-2">
                    <span className="inline-flex items-center">
                      {t("fundamentals.value_col")}
                      <InfoTooltip title={t("tooltips.garp_val_score_title")} content={t("tooltips.garp_val_score_desc")} />
                    </span>
                  </th>
                  <th className="pb-2">
                    <span className="inline-flex items-center">
                      {t("fundamentals.roic_label")}
                      <InfoTooltip title={t("tooltips.roic_title")} content={t("tooltips.roic_desc")} />
                    </span>
                  </th>
                  <th className="pb-2 text-right">
                    <span className="inline-flex items-center justify-end w-full">
                      {t("tooltips.ev_ebitda_title")}
                      <InfoTooltip title={t("tooltips.ev_ebitda_title")} content={t("tooltips.ev_ebitda_desc")} />
                    </span>
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border/40">
                {screener.map((item) => (
                  <tr
                    key={item.symbol}
                    onClick={() => setSelectedSymbol(item.symbol)}
                    className="hover:bg-surface-2 cursor-pointer transition-colors"
                  >
                    <td className="py-2.5 font-bold text-text-1">{item.symbol}</td>
                    <td className="py-2.5 text-text-3 text-[11px]">{item.sector}</td>
                    <td className="py-2.5 text-pos font-semibold">
                      {(item.quality_score * 100).toFixed(0)}
                    </td>
                    <td className="py-2.5 text-info font-semibold">
                      {(item.value_score * 100).toFixed(0)}
                    </td>
                    <td className="py-2.5 text-text-2">{(item.roic * 100).toFixed(1)}%</td>
                    <td className="py-2.5 text-right text-text-2">{item.ev_ebitda.toFixed(1)}x</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </div>
  );
}
