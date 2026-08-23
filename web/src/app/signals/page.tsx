"use client";

import { useEffect, useState } from "react";
import { api, SignalExploreData } from "@/lib/api";
import { ChartCanvas } from "@/components/ChartCanvas";
import { MetricCard } from "@/components/MetricCard";
import { InfoTooltip } from "@/components/Tooltip";
import { TrendingUp, Search, Sliders, Activity } from "lucide-react";

export default function SignalsExplorerPage() {
  const [symbol, setSymbol] = useState("SPY");
  const [inputVal, setInputVal] = useState("SPY");
  const [data, setData] = useState<SignalExploreData | null>(null);
  const [activeIndicator, setActiveIndicator] = useState("rsi_14");
  const [loading, setLoading] = useState(false);

  const fetchSignals = async (sym: string) => {
    setLoading(true);
    const result = await api.exploreSignals(sym);
    setData(result);
    setLoading(false);
  };

  useEffect(() => {
    fetchSignals(symbol);
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
  const volumeChartData = points.map((p) => ({ ts: p.ts, value: p.volume }));

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

  return (
    <div className="space-y-6">
      {/* Top Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-border pb-5">
        <div>
          <h1 className="text-xl font-bold font-mono tracking-tight text-text-1">
            SIGNALS EXPLORER
          </h1>
          <p className="text-xs text-text-2 font-mono mt-1">
            Point-in-time price analysis, multi-layer feature calculation, and indicator inspection.
          </p>
        </div>

        {/* Ticker Search Bar */}
        <form onSubmit={handleSearch} className="flex items-center gap-2">
          <div className="relative">
            <input
              type="text"
              value={inputVal}
              onChange={(e) => setInputVal(e.target.value.toUpperCase())}
              placeholder="SYMBOL (e.g. SPY)"
              className="bg-surface-2 border border-border focus:border-pos focus:outline-none rounded px-3 py-1.5 text-xs font-mono text-text-1 uppercase w-36"
            />
          </div>
          <button type="submit" className="btn-primary">
            <Search className="w-3.5 h-3.5" />
            <span>QUERY</span>
          </button>
        </form>
      </div>

      {/* Symbol Quick Stats */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
        <MetricCard
          label={`CLOSE (${symbol})`}
          value={`$${latestClose.toFixed(2)}`}
          subValue={latestPoint ? new Date(latestPoint.ts).toLocaleDateString() : ""}
          tooltip={`Latest observed adjusted closing price for ticker ${symbol}.`}
          tooltipTitle="Closing Price"
        />
        <MetricCard
          label="RSI (14)"
          value={latestRsi.toFixed(1)}
          direction={latestRsi < 30 ? "pos" : latestRsi > 70 ? "neg" : "neutral"}
          subValue={latestRsi < 30 ? "Oversold (<30)" : latestRsi > 70 ? "Overbought (>70)" : "Neutral"}
          tooltip="Relative Strength Index (14-day): Measures momentum on a 0–100 scale. Below 30 means heavily sold (bargain bounce zone), above 70 means overbought (stretched)."
          tooltipTitle="RSI (Relative Strength Index)"
        />
        <MetricCard
          label="200-DAY SMA"
          value={`$${latestSma200.toFixed(2)}`}
          direction={latestClose > latestSma200 ? "pos" : "neg"}
          subValue={latestClose > latestSma200 ? "Above 200 SMA (Bullish)" : "Below 200 SMA"}
          tooltip="200-Day Simple Moving Average: The benchmark long-term trend line (~10 months). Stock trading above this line is in an overall uptrend."
          tooltipTitle="200-Day Moving Average"
        />
        <MetricCard
          label="MACD OSCILLATOR"
          value={latestMacd.toFixed(2)}
          direction={latestMacd > 0 ? "pos" : "neg"}
          subValue={latestMacd > 0 ? "Positive Momentum" : "Negative Momentum"}
          tooltip="Moving Average Convergence Divergence: Compares 12-day and 26-day price trends. Positive values indicate accelerating upward price momentum."
          tooltipTitle="MACD Momentum"
        />
      </div>

      {/* Main Price Chart */}
      <div className="space-y-4">
        <ChartCanvas
          data={priceChartData}
          label={`${symbol} Daily Close Price ($)`}
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
              INDICATOR SUB-PANEL: {activeIndicator.toUpperCase()}
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
    </div>
  );
}
