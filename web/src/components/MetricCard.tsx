"use client";

interface MetricCardProps {
  label: string;
  value: string | number;
  subValue?: string;
  direction?: "pos" | "neg" | "neutral";
  mono?: boolean;
}

export function MetricCard({
  label,
  value,
  subValue,
  direction = "neutral",
  mono = true,
}: MetricCardProps) {
  let valueColor = "text-text-1";
  if (direction === "pos") valueColor = "text-pos";
  if (direction === "neg") valueColor = "text-neg";

  return (
    <div className="card-panel">
      <div className="terminal-label mb-1.5">{label}</div>
      <div className={`text-xl font-semibold tracking-tight ${mono ? "font-mono" : ""} ${valueColor}`}>
        {value}
      </div>
      {subValue && <div className="text-[11px] font-mono text-text-3 mt-1">{subValue}</div>}
    </div>
  );
}
