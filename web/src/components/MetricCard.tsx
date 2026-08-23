"use client";

import { InfoTooltip } from "./Tooltip";

interface MetricCardProps {
  label: string;
  value: string | number;
  subValue?: string;
  direction?: "pos" | "neg" | "neutral";
  mono?: boolean;
  tooltip?: string;
  tooltipTitle?: string;
}

export function MetricCard({
  label,
  value,
  subValue,
  direction = "neutral",
  mono = true,
  tooltip,
  tooltipTitle,
}: MetricCardProps) {
  let valueColor = "text-text-1";
  if (direction === "pos") valueColor = "text-pos";
  if (direction === "neg") valueColor = "text-neg";

  return (
    <div className="card-panel">
      <div className="flex items-center justify-between mb-1.5">
        <div className="terminal-label">{label}</div>
        {tooltip && <InfoTooltip content={tooltip} title={tooltipTitle || label} />}
      </div>
      <div
        className={`text-xl font-semibold tracking-tight ${mono ? "font-mono" : ""} ${valueColor}`}
      >
        {value}
      </div>
      {subValue && <div className="text-[11px] font-mono text-text-3 mt-1">{subValue}</div>}
    </div>
  );
}
