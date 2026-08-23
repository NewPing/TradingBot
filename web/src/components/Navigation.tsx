"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  Activity,
  Layers,
  GitCompare,
  TrendingUp,
  Terminal,
  Radio,
  Cpu,
  FileSpreadsheet,
  Newspaper,
  FlaskConical,
  BookOpen,
  Sparkles,
} from "lucide-react";
import { InfoTooltip } from "./Tooltip";
import { LanguageSwitch } from "./LanguageSwitch";
import { useTranslation } from "@/i18n";
import { useWalkthrough } from "./WalkthroughContext";

export function Navigation() {
  const pathname = usePathname();
  const { t } = useTranslation();
  const { openWalkthrough } = useWalkthrough();

  const navItems = [
    { href: "/", label: t("nav.overview"), icon: Activity },
    { href: "/live", label: t("nav.live"), icon: Radio },
    { href: "/versions", label: t("nav.versions"), icon: Layers },
    { href: "/compare", label: t("nav.compare"), icon: GitCompare },
    { href: "/signals", label: t("nav.signals"), icon: TrendingUp },
    { href: "/models", label: t("nav.models"), icon: Cpu },
    { href: "/fundamentals", label: t("nav.fundamentals"), icon: FileSpreadsheet },
    { href: "/narrative", label: t("nav.narrative"), icon: Newspaper },
    { href: "/research", label: t("nav.research"), icon: FlaskConical },
    { href: "/docs", label: t("nav.docs"), icon: BookOpen },
  ];

  return (
    <aside className="w-64 bg-bg-sidebar border-r border-border flex flex-col justify-between p-4 shrink-0 h-screen sticky top-0">
      <div className="space-y-4">
        {/* Brand Header */}
        <div className="flex items-center gap-3 px-2 py-1">
          <div className="w-8 h-8 rounded bg-surface-2 border border-border flex items-center justify-center text-pos">
            <Terminal className="w-4 h-4" />
          </div>
          <div>
            <div className="text-sm font-bold tracking-tight text-text-1 font-mono">
              {t("common.system_name")}<span className="text-pos font-normal">::v1</span>
            </div>
            <div className="text-[10px] text-text-3 font-mono">{t("common.system_tagline")}</div>
          </div>
        </div>

        {/* Language Switcher */}
        <LanguageSwitch />

        {/* Quick Tour / Walkthrough Button */}
        <button
          onClick={() => openWalkthrough(0)}
          className="w-full flex items-center justify-center gap-2 px-3 py-2 rounded bg-pos/10 border border-pos/40 text-pos hover:bg-pos/20 text-xs font-mono font-bold transition-all shadow-sm group"
        >
          <Sparkles className="w-3.5 h-3.5 text-pos group-hover:scale-110 transition-transform" />
          <span>{t("nav.walkthrough_btn")}</span>
        </button>

        {/* Status Indicator */}
        <div className="bg-surface border border-border rounded p-2.5 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <span className="w-2 h-2 rounded-full bg-pos animate-pulse" />
            <span className="text-xs font-mono text-text-2">{t("common.engine_ready")}</span>
          </div>
          <span className="text-[10px] font-mono text-text-3">{t("common.port_label")}</span>
        </div>

        {/* Nav Links */}
        <nav className="space-y-1 overflow-y-auto max-h-[calc(100vh-340px)] pr-1">
          <div className="terminal-label px-2 mb-2">{t("nav.system_views")}</div>
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
            <span>{t("nav.parity")}</span>
            <InfoTooltip
              title={t("tooltips.parity_title")}
              content={t("tooltips.parity_desc")}
              side="right"
            />
          </div>
          <span className="text-pos font-semibold">{t("common.enforced")}</span>
        </div>
        <div className="flex items-center justify-between">
          <div className="flex items-center">
            <span>{t("nav.lookahead")}</span>
            <InfoTooltip
              title={t("tooltips.lookahead_title")}
              content={t("tooltips.lookahead_desc")}
              side="right"
            />
          </div>
          <span className="text-pos font-semibold">{t("common.zero")}</span>
        </div>
        <div className="flex items-center justify-between">
          <div className="flex items-center">
            <span>{t("nav.live_trading")}</span>
            <InfoTooltip
              title={t("tooltips.live_safety_title")}
              content={t("tooltips.live_safety_desc")}
              side="right"
            />
          </div>
          <span className="text-text-3">{t("common.locked")}</span>
        </div>
      </div>
    </aside>
  );
}
