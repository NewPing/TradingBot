"use client";

import { useEffect, useState } from "react";
import { api, SignalExploreData, UniverseCandidate, UniverseScreenerResponse } from "@/lib/api";
import { ChartCanvas } from "@/components/ChartCanvas";
import { MetricCard } from "@/components/MetricCard";
import { InfoTooltip } from "@/components/Tooltip";
import { StrategyBlueprint } from "@/components/StrategyBlueprint";
import { useTranslation } from "@/i18n";
import {
  TrendingUp,
  Search,
  Sliders,
  Activity,
  ShieldCheck,
  CheckCircle2,
  XCircle,
  Filter,
  DollarSign,
  Layers,
} from "lucide-react";

export default function SignalsExplorerPage() {
  const { t } = useTranslation();
  const [symbol, setSymbol] = useState("SPY");
  const [inputVal, setInputVal] = useState("SPY");
  const [data, setData] = useState<SignalExploreData | null>(null);
  const [activeIndicator, setActiveIndicator] = useState("rsi_14");
  const [screener, setScreener] = useState<UniverseScreenerResponse | null>(null);
  const [screenerFilter, setScreenerFilter] = useState<string>("ALL");
  const [loading, setLoading] = useState(false);

  const fetchSignals = async (sym: string) => {
    setLoading(true);
    const result = await api.exploreSignals(sym);
    setData(result);
    setLoading(false);
  };

  useEffect(() => {
    fetchSignals(symbol);
    api.getUniverseScreener().then((res) => {
      if (res) setScreener(res);
    });
  }, [symbol]);

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault();
    if (inputVal.trim()) {
      setSymbol(inputVal.trim().toUpperCase());
    }
  };

  const points = data?.points || [];
  const priceChartData = points.map((p) => ({ ts: p.ts, value: p.close }));
  const indicatorChartData = points.map((p) => ({
    ts: p.ts,
    value: p.signals[activeIndicator] ?? 0,
  }));

  const latestPoint = points[points.length - 1];
  const latestClose = latestPoint ? latestPoint.close : 0;
  const latestRsi = latestPoint?.signals["rsi_14"] ?? 0;
  const latestSma200 = latestPoint?.signals["sma_200"] ?? 0;
  const latestMacd = latestPoint?.signals["macd"] ?? 0;

  const indicators = [
    { key: "rsi_14", label: "RSI (14)" },
    { key: "macd", label: "MACD" },
    { key: "momentum_20", label: "MOMENTUM (20)" },
    { key: "atr_14", label: "ATR (14)" },
    { key: "sma_20", label: "SMA 20" },
    { key: "sma_50", label: "SMA 50" },
    { key: "sma_200", label: "SMA 200" },
  ];

  const filteredCandidates = screener
    ? screener.candidates.filter((c) => {
        if (screenerFilter === "QUALIFIED") return c.status === "QUALIFIED";
        if (screenerFilter === "FILTERED") return c.status !== "QUALIFIED";
        return true;
      })
    : [];

  return (
    <div className="space-y-6">
      {/* Top Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-border pb-5">
        <div>
          <div className="flex items-center gap-2">
            <h1 className="text-xl font-bold font-mono tracking-tight text-text-1">
              {t("signals.title")}
            </h1>
            <span className="badge-terminal bg-surface-2 text-pos border border-border">
              L1-L4
            </span>
            <InfoTooltip
              title="Alpha Signals & Universe Intelligence"
              content="Layer 1 through 4 quantitative signal computation, dynamic universe liquidity screening, and technical indicators executing strictly without lookahead."
            />
          </div>
          <p className="text-xs text-text-2 font-mono mt-1">
            {t("signals.subtitle")}
          </p>
        </div>

        {/* Ticker Search Bar */}
        <form onSubmit={handleSearch} className="flex items-center gap-2">
          <div className="relative">
            <input
              type="text"
              value={inputVal}
              onChange={(e) => setInputVal(e.target.value.toUpperCase())}
              placeholder={t("signals.search_placeholder")}
              className="bg-surface-2 border border-border focus:border-pos focus:outline-none rounded px-3 py-1.5 text-xs font-mono text-text-1 uppercase w-36"
            />
          </div>
          <button type="submit" className="btn-primary">
            <Search className="w-3.5 h-3.5" />
            <span>{t("common.search")}</span>
          </button>
        </form>
      </div>

      {/* Symbol Quick Stats */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
        <MetricCard
          label={`${t("signals.close_label")} (${symbol})`}
          value={`$${latestClose.toFixed(2)}`}
          subValue={latestPoint ? new Date(latestPoint.ts).toLocaleDateString() : ""}
          tooltip={t("tooltips.close_price_desc")}
          tooltipTitle={t("tooltips.close_price_title")}
        />
        <MetricCard
          label={t("signals.rsi_label")}
          value={latestRsi.toFixed(1)}
          direction={latestRsi < 30 ? "pos" : latestRsi > 70 ? "neg" : "neutral"}
          subValue={
            latestRsi < 30
              ? t("signals.oversold_sub")
              : latestRsi > 70
              ? t("signals.overbought_sub")
              : t("signals.neutral_sub")
          }
          tooltip={t("tooltips.rsi_desc")}
          tooltipTitle={t("tooltips.rsi_title")}
        />
        <MetricCard
          label={t("signals.sma200_label")}
          value={`$${latestSma200.toFixed(2)}`}
          direction={latestClose > latestSma200 ? "pos" : "neg"}
          subValue={
            latestClose > latestSma200
              ? t("signals.above_sma_sub")
              : t("signals.below_sma_sub")
          }
          tooltip={t("tooltips.sma200_desc")}
          tooltipTitle={t("tooltips.sma200_title")}
        />
        <MetricCard
          label={t("signals.macd_label")}
          value={latestMacd.toFixed(2)}
          direction={latestMacd > 0 ? "pos" : "neg"}
          subValue={
            latestMacd > 0
              ? t("signals.pos_momentum_sub")
              : t("signals.neg_momentum_sub")
          }
          tooltip={t("tooltips.macd_desc")}
          tooltipTitle={t("tooltips.macd_title")}
        />
      </div>

      {/* Main Price Chart */}
      <div className="space-y-4">
        <ChartCanvas
          data={priceChartData}
          label={`${symbol} ${t("signals.daily_close_chart")}`}
          height={260}
          color="#22c55e"
          formatValue={(v) => `$${v.toFixed(2)}`}
        />
      </div>

      {/* Sub-panel Indicator Selector & Chart */}
      <div className="card-panel space-y-4">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
          <div className="flex items-center gap-2">
            <Sliders className="w-4 h-4 text-pos" />
            <span className="text-xs font-mono font-semibold text-text-1">
              {t("signals.indicator_subpanel")}: {activeIndicator.toUpperCase()}
            </span>
          </div>

          {/* Indicator Pills */}
          <div className="flex items-center gap-1.5 overflow-x-auto">
            {indicators.map((ind) => (
              <button
                key={ind.key}
                onClick={() => setActiveIndicator(ind.key)}
                className={`px-2.5 py-1 rounded text-[11px] font-mono transition-all ${
                  activeIndicator === ind.key
                    ? "bg-active border border-pos text-pos font-semibold"
                    : "bg-surface-2 border border-border text-text-3 hover:text-text-1"
                }`}
              >
                {ind.label}
              </button>
            ))}
          </div>
        </div>

        <ChartCanvas
          data={indicatorChartData}
          label={`${symbol} · ${activeIndicator.toUpperCase()}`}
          height={160}
          color="#38bdf8"
          formatValue={(v) => v.toFixed(2)}
        />
      </div>

      {/* Algorithmic Universe Selection Screener Panel */}
      {screener && (
        <div className="card-panel space-y-4">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-border pb-3">
            <div className="flex items-center gap-2">
              <ShieldCheck className="w-4 h-4 text-pos" />
              <div>
                <h3 className="text-xs font-bold font-mono text-text-1 uppercase tracking-wider">
                  Algorithmic Universe Selection & Liquidity Screener
                </h3>
                <p className="text-[11px] font-mono text-text-3">
                  Screening rules: ADV(20) &ge; ${((screener.min_adv_usd) / 1_000_000).toFixed(0)}M · Price &ge; ${screener.min_price_usd.toFixed(2)} · ROIC &ge; 8% · Piotroski &ge; 6
                </p>
              </div>
            </div>

            {/* Filter Pills */}
            <div className="flex items-center gap-1 bg-surface-2 p-1 rounded border border-border">
              <button
                onClick={() => setScreenerFilter("ALL")}
                className={`px-2.5 py-0.5 text-[11px] font-mono rounded transition-all ${
                  screenerFilter === "ALL"
                    ? "bg-surface-3 text-text-1 font-semibold border border-border"
                    : "text-text-3 hover:text-text-1"
                }`}
              >
                All ({screener.total_evaluated})
              </button>
              <button
                onClick={() => setScreenerFilter("QUALIFIED")}
                className={`px-2.5 py-0.5 text-[11px] font-mono rounded transition-all ${
                  screenerFilter === "QUALIFIED"
                    ? "bg-surface-3 text-pos font-semibold border border-border"
                    : "text-text-3 hover:text-text-1"
                }`}
              >
                Qualified ({screener.qualified_count})
              </button>
              <button
                onClick={() => setScreenerFilter("FILTERED")}
                className={`px-2.5 py-0.5 text-[11px] font-mono rounded transition-all ${
                  screenerFilter === "FILTERED"
                    ? "bg-surface-3 text-neg font-semibold border border-border"
                    : "text-text-3 hover:text-text-1"
                }`}
              >
                Filtered ({screener.filtered_count})
              </button>
            </div>
          </div>

          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs font-mono">
              <thead>
                <tr className="border-b border-border text-text-3 text-[10px] uppercase">
                  <th className="pb-2.5 pl-2">Symbol</th>
                  <th className="pb-2.5">Price</th>
                  <th className="pb-2.5">20-day ADV ($)</th>
                  <th className="pb-2.5">ROIC (%)</th>
                  <th className="pb-2.5">Piotroski F-Score</th>
                  <th className="pb-2.5">Liquidity Status</th>
                  <th className="pb-2.5 pr-2 text-right">Universe Eligibility</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {filteredCandidates.map((c) => (
                  <tr
                    key={c.symbol}
                    className="hover:bg-surface-2 transition-colors cursor-pointer"
                    onClick={() => {
                      setSymbol(c.symbol);
                      setInputVal(c.symbol);
                    }}
                  >
                    <td className="py-2.5 pl-2 font-bold text-text-1">{c.symbol}</td>
                    <td className="py-2.5 text-text-2">${c.price.toFixed(2)}</td>
                    <td className="py-2.5 text-text-2">
                      ${(c.adv_20_usd / 1_000_000).toLocaleString(undefined, { maximumFractionDigits: 1 })}M
                    </td>
                    <td className="py-2.5 text-text-2">
                      {c.roic_pct !== undefined ? `${c.roic_pct.toFixed(1)}%` : "N/A"}
                    </td>
                    <td className="py-2.5 text-text-2">
                      {c.piotroski_f_score !== undefined ? `${c.piotroski_f_score}/9` : "N/A"}
                    </td>
                    <td className="py-2.5">
                      <span
                        className={`inline-flex items-center gap-1 text-[11px] ${
                          c.is_liquid ? "text-pos font-semibold" : "text-neg font-semibold"
                        }`}
                      >
                        {c.is_liquid ? <CheckCircle2 className="w-3 h-3" /> : <XCircle className="w-3 h-3" />}
                        {c.is_liquid ? "ADV >= $20M" : "Illiquid (< $20M)"}
                      </span>
                    </td>
                    <td className="py-2.5 pr-2 text-right">
                      <span
                        className={`terminal-badge ${
                          c.status === "QUALIFIED"
                            ? "bg-pos/15 text-pos border border-pos/30"
                            : "bg-neg/15 text-neg border border-neg/30"
                        }`}
                      >
                        {c.status}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Strategy Blueprint & Multi-Phase Execution Architecture */}
      <StrategyBlueprint />
    </div>
  );
}
