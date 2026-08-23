"use client";

import { useMemo } from "react";
import { useTranslation } from "@/i18n";

interface Point {
  ts: string;
  value: number;
}

interface ChartCanvasProps {
  data: Point[];
  label?: string;
  height?: number;
  color?: string;
  formatValue?: (v: number) => string;
  isDrawdown?: boolean;
}

export function ChartCanvas({
  data,
  label,
  height = 200,
  color = "#22c55e",
  formatValue = (v) => v.toFixed(2),
  isDrawdown = false,
}: ChartCanvasProps) {
  const { t } = useTranslation();
  const displayLabel = label ?? t("chart.series");
  const { pathD, minVal, maxVal, firstVal, lastVal, pctChange } = useMemo(() => {
    if (!data || data.length === 0) {
      return { pathD: "", minVal: 0, maxVal: 0, firstVal: 0, lastVal: 0, pctChange: 0 };
    }

    const values = data.map((d) => d.value);
    const min = isDrawdown ? Math.min(0, ...values) : Math.min(...values);
    const max = isDrawdown ? 0 : Math.max(...values);
    const range = max - min || 1;

    const width = 800;
    const padding = 20;
    const usableWidth = width - padding * 2;
    const usableHeight = height - padding * 2;

    const coords = data.map((d, i) => {
      const x = padding + (i / (data.length - 1 || 1)) * usableWidth;
      const normalizedY = (d.value - min) / range;
      const y = height - padding - normalizedY * usableHeight;
      return `${x.toFixed(1)},${y.toFixed(1)}`;
    });

    const path = coords.length > 0 ? `M ${coords.join(" L ")}` : "";
    const first = values[0] || 0;
    const last = values[values.length - 1] || 0;
    const change = first !== 0 ? ((last - first) / Math.abs(first)) * 100 : 0;

    return {
      pathD: path,
      minVal: min,
      maxVal: max,
      firstVal: first,
      lastVal: last,
      pctChange: change,
    };
  }, [data, height, isDrawdown]);

  if (!data || data.length === 0) {
    return (
      <div
        style={{ height }}
        className="w-full flex items-center justify-center border border-dashed border-border rounded bg-surface-2 text-text-3 text-xs font-mono"
      >
        {t("common.no_data")}
      </div>
    );
  }

  return (
    <div className="w-full bg-surface border border-border rounded p-4">
      <div className="flex items-center justify-between mb-2">
        <div className="flex items-center gap-2">
          <span className="text-xs font-mono font-medium text-text-1">{displayLabel}</span>
          {!isDrawdown && (
            <span
              className={`text-[11px] font-mono px-1.5 py-0.5 rounded ${
                pctChange >= 0
                  ? "bg-surface-2 text-pos border border-border"
                  : "bg-surface-2 text-neg border border-border"
              }`}
            >
              {pctChange >= 0 ? "+" : ""}
              {pctChange.toFixed(2)}%
            </span>
          )}
        </div>
        <div className="text-xs font-mono text-text-2">
          {formatValue(lastVal)}
        </div>
      </div>

      <div className="relative w-full overflow-hidden" style={{ height }}>
        <svg
          viewBox={`0 0 800 ${height}`}
          className="w-full h-full overflow-visible"
          preserveAspectRatio="none"
        >
          {/* Grid lines */}
          <line
            x1="20"
            y1="20"
            x2="780"
            y2="20"
            stroke="#262626"
            strokeDasharray="3 3"
            strokeWidth="1"
          />
          <line
            x1="20"
            y1={height / 2}
            x2="780"
            y2={height / 2}
            stroke="#262626"
            strokeDasharray="3 3"
            strokeWidth="1"
          />
          <line
            x1="20"
            y1={height - 20}
            x2="780"
            y2={height - 20}
            stroke="#262626"
            strokeDasharray="3 3"
            strokeWidth="1"
          />

          {/* Sparkline curve */}
          <path
            d={pathD}
            fill="none"
            stroke={color}
            strokeWidth="2"
            strokeLinecap="round"
            strokeLinejoin="round"
          />
        </svg>
      </div>

      <div className="flex items-center justify-between text-[10px] font-mono text-text-3 mt-1">
        <span>{t("chart.min")}: {formatValue(minVal)}</span>
        <span>{data.length} {t("chart.bars")}</span>
        <span>{t("chart.max")}: {formatValue(maxVal)}</span>
      </div>
    </div>
  );
}
