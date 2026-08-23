"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  Activity,
  Layers,
  GitCompare,
  TrendingUp,
  Terminal,
} from "lucide-react";
import { InfoTooltip } from "./Tooltip";

export function Navigation() {
  const pathname = usePathname();

  const navItems = [
    { href: "/", label: "Overview", icon: Activity },
    { href: "/versions", label: "Versions & Lineage", icon: Layers },
    { href: "/compare", label: "Compare Runs", icon: GitCompare },
    { href: "/signals", label: "Signals Explorer", icon: TrendingUp },
  ];

  return (
    <aside className="w-64 bg-bg-sidebar border-r border-border flex flex-col justify-between p-4 shrink-0 h-screen sticky top-0">
      <div className="space-y-6">
        {/* Brand Header */}
        <div className="flex items-center gap-3 px-2 py-1">
          <div className="w-8 h-8 rounded bg-surface-2 border border-border flex items-center justify-center text-pos">
            <Terminal className="w-4 h-4" />
          </div>
          <div>
            <div className="text-sm font-bold tracking-tight text-text-1 font-mono">
              ATLAS<span className="text-pos font-normal">::v1</span>
            </div>
            <div className="text-[10px] text-text-3 font-mono">AUTONOMOUS QUANT</div>
          </div>
        </div>

        {/* Status Indicator */}
        <div className="bg-surface border border-border rounded p-2.5 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <span className="w-2 h-2 rounded-full bg-pos animate-pulse" />
            <span className="text-xs font-mono text-text-2">Engine Ready</span>
          </div>
          <span className="text-[10px] font-mono text-text-3">PORT 8001</span>
        </div>

        {/* Nav Links */}
        <nav className="space-y-1">
          <div className="terminal-label px-2 mb-2">SYSTEM VIEWS</div>
          {navItems.map((item) => {
            const Icon = item.icon;
            const isActive = pathname === item.href;
            return (
              <Link
                key={item.href}
                href={item.href}
                className={`flex items-center gap-2.5 px-3 py-2 rounded text-xs font-mono transition-all ${
                  isActive
                    ? "bg-active text-text-1 border border-border border-l-2 border-l-pos font-semibold"
                    : "text-text-2 hover:bg-surface-2 hover:text-text-1 border border-transparent"
                }`}
              >
                <Icon className={`w-4 h-4 ${isActive ? "text-pos" : "text-text-3"}`} />
                <span>{item.label}</span>
              </Link>
            );
          })}
        </nav>
      </div>

      {/* Footer Info */}
      <div className="border-t border-border pt-3 space-y-2 text-[11px] font-mono text-text-3">
        <div className="flex items-center justify-between">
          <div className="flex items-center">
            <span>PARITY</span>
            <InfoTooltip
              title="Code Parity"
              content="Backtest, paper simulation, and live modes execute the exact same trading logic and risk checks. Only the clock and broker connector change."
              side="right"
            />
          </div>
          <span className="text-pos font-semibold">ENFORCED</span>
        </div>
        <div className="flex items-center justify-between">
          <div className="flex items-center">
            <span>LOOKAHEAD</span>
            <InfoTooltip
              title="Zero Lookahead Bias"
              content="Signals and decisions can only see historical market bars up to the exact simulated moment (t <= clock.now). Future price data is completely blocked."
              side="right"
            />
          </div>
          <span className="text-pos font-semibold">ZERO</span>
        </div>
        <div className="flex items-center justify-between">
          <div className="flex items-center">
            <span>LIVE TRADING</span>
            <InfoTooltip
              title="Live Safety Lock"
              content="Real-money execution is disabled at the root configuration level. Strategies must first pass 90 days of paper trading and validation gates."
              side="right"
            />
          </div>
          <span className="text-text-3">LOCKED</span>
        </div>
      </div>
    </aside>
  );
}
