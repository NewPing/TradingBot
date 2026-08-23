"use client";

import { useState, useEffect } from "react";
import Link from "next/link";
import {
  Terminal,
  Activity,
  Layers,
  Cpu,
  FileSpreadsheet,
  Newspaper,
  FlaskConical,
  Radio,
  ShieldCheck,
  ShieldAlert,
  ArrowRight,
  ArrowLeft,
  X,
  BookOpen,
  CheckCircle2,
  Sparkles,
  Zap,
  Lock,
} from "lucide-react";
import { useTranslation } from "@/i18n";

interface WalkthroughModalProps {
  isOpen: boolean;
  initialStep?: number;
  onClose: () => void;
}

export function WalkthroughModal({
  isOpen,
  initialStep = 0,
  onClose,
}: WalkthroughModalProps) {
  const { t } = useTranslation();
  const [step, setStep] = useState(initialStep);

  useEffect(() => {
    if (isOpen) {
      setStep(initialStep);
    }
  }, [isOpen, initialStep]);

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (!isOpen) return;
      if (e.key === "Escape") onClose();
      if (e.key === "ArrowRight") setStep((s) => Math.min(s + 1, 5));
      if (e.key === "ArrowLeft") setStep((s) => Math.max(s - 1, 0));
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [isOpen, onClose]);

  if (!isOpen) return null;

  const totalSteps = 6;

  const slides = [
    {
      id: "architecture",
      icon: Terminal,
      badge: "SYSTEM ARCHITECTURE",
      title: t("walkthrough.slide_1_title"),
      subtitle: t("walkthrough.slide_1_subtitle"),
      content: (
        <div className="space-y-4">
          <p className="text-xs text-text-2 leading-relaxed">
            {t("walkthrough.slide_1_desc")}
          </p>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 text-xs font-mono">
            <div className="p-3 bg-surface-2 border border-border rounded">
              <div className="text-pos font-bold flex items-center gap-1.5 mb-1">
                <CheckCircle2 className="w-3.5 h-3.5" />
                {t("walkthrough.slide_1_parity_title")}
              </div>
              <p className="text-text-3 text-[11px] leading-relaxed">
                {t("walkthrough.slide_1_parity_desc")}
              </p>
            </div>
            <div className="p-3 bg-surface-2 border border-border rounded">
              <div className="text-pos font-bold flex items-center gap-1.5 mb-1">
                <ShieldCheck className="w-3.5 h-3.5" />
                {t("walkthrough.slide_1_lookahead_title")}
              </div>
              <p className="text-text-3 text-[11px] leading-relaxed">
                {t("walkthrough.slide_1_lookahead_desc")}
              </p>
            </div>
            <div className="p-3 bg-surface-2 border border-border rounded">
              <div className="text-info font-bold flex items-center gap-1.5 mb-1">
                <Layers className="w-3.5 h-3.5" />
                {t("walkthrough.slide_1_buckets_title")}
              </div>
              <p className="text-text-3 text-[11px] leading-relaxed">
                {t("walkthrough.slide_1_buckets_desc")}
              </p>
            </div>
            <div className="p-3 bg-surface-2 border border-border rounded">
              <div className="text-warn font-bold flex items-center gap-1.5 mb-1">
                <ShieldAlert className="w-3.5 h-3.5" />
                {t("walkthrough.slide_1_risk_title")}
              </div>
              <p className="text-text-3 text-[11px] leading-relaxed">
                {t("walkthrough.slide_1_risk_desc")}
              </p>
            </div>
          </div>
        </div>
      ),
    },
    {
      id: "alpha_stack",
      icon: Activity,
      badge: "THE 4 ALPHA LAYERS",
      title: t("walkthrough.slide_2_title"),
      subtitle: t("walkthrough.slide_2_subtitle"),
      content: (
        <div className="space-y-4">
          <p className="text-xs text-text-2 leading-relaxed">
            {t("walkthrough.slide_2_desc")}
          </p>
          <div className="space-y-2 text-xs font-mono">
            <div className="p-2.5 bg-surface-2 border border-border rounded flex items-start gap-3">
              <span className="px-1.5 py-0.5 rounded bg-surface text-pos font-bold text-[10px] shrink-0 border border-border">
                L1
              </span>
              <div>
                <span className="font-bold text-text-1">{t("walkthrough.slide_2_l1_title")}: </span>
                <span className="text-text-3 text-[11px]">{t("walkthrough.slide_2_l1_desc")}</span>
              </div>
            </div>
            <div className="p-2.5 bg-surface-2 border border-border rounded flex items-start gap-3">
              <span className="px-1.5 py-0.5 rounded bg-surface text-info font-bold text-[10px] shrink-0 border border-border">
                L2
              </span>
              <div>
                <span className="font-bold text-text-1">{t("walkthrough.slide_2_l2_title")}: </span>
                <span className="text-text-3 text-[11px]">{t("walkthrough.slide_2_l2_desc")}</span>
              </div>
            </div>
            <div className="p-2.5 bg-surface-2 border border-border rounded flex items-start gap-3">
              <span className="px-1.5 py-0.5 rounded bg-surface text-warn font-bold text-[10px] shrink-0 border border-border">
                L3
              </span>
              <div>
                <span className="font-bold text-text-1">{t("walkthrough.slide_2_l3_title")}: </span>
                <span className="text-text-3 text-[11px]">{t("walkthrough.slide_2_l3_desc")}</span>
              </div>
            </div>
            <div className="p-2.5 bg-surface-2 border border-border rounded flex items-start gap-3">
              <span className="px-1.5 py-0.5 rounded bg-surface text-purple-400 font-bold text-[10px] shrink-0 border border-border">
                L4
              </span>
              <div>
                <span className="font-bold text-text-1">{t("walkthrough.slide_2_l4_title")}: </span>
                <span className="text-text-3 text-[11px]">{t("walkthrough.slide_2_l4_desc")}</span>
              </div>
            </div>
          </div>
        </div>
      ),
    },
    {
      id: "immutability",
      icon: Layers,
      badge: "SCIENTIFIC RIGOR",
      title: t("walkthrough.slide_3_title"),
      subtitle: t("walkthrough.slide_3_subtitle"),
      content: (
        <div className="space-y-4">
          <p className="text-xs text-text-2 leading-relaxed">
            {t("walkthrough.slide_3_desc")}
          </p>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3 text-xs font-mono">
            <div className="p-3 bg-surface-2 border border-border rounded space-y-1.5">
              <div className="text-text-1 font-bold flex items-center gap-1.5">
                <Lock className="w-3.5 h-3.5 text-pos" />
                {t("walkthrough.slide_3_immutability_title")}
              </div>
              <p className="text-text-3 text-[11px] leading-relaxed">
                {t("walkthrough.slide_3_immutability_desc")}
              </p>
            </div>
            <div className="p-3 bg-surface-2 border border-border rounded space-y-1.5">
              <div className="text-text-1 font-bold flex items-center gap-1.5">
                <Activity className="w-3.5 h-3.5 text-info" />
                {t("walkthrough.slide_3_repro_title")}
              </div>
              <p className="text-text-3 text-[11px] leading-relaxed">
                {t("walkthrough.slide_3_repro_desc")}
              </p>
            </div>
          </div>
          <div className="p-2.5 bg-active border border-border-subtle rounded text-[11px] font-mono text-text-2 flex items-center justify-between">
            <span>{t("walkthrough.slide_3_footer_tip")}</span>
            <Link
              href="/versions"
              onClick={onClose}
              className="text-pos hover:underline text-[11px] font-bold"
            >
              {t("nav.versions")} &rarr;
            </Link>
          </div>
        </div>
      ),
    },
    {
      id: "research_loop",
      icon: FlaskConical,
      badge: "RESEARCH AUTOMATION",
      title: t("walkthrough.slide_4_title"),
      subtitle: t("walkthrough.slide_4_subtitle"),
      content: (
        <div className="space-y-4">
          <p className="text-xs text-text-2 leading-relaxed">
            {t("walkthrough.slide_4_desc")}
          </p>
          <div className="p-3 bg-surface-2 border border-border rounded space-y-2 text-xs font-mono">
            <div className="text-pos font-bold flex items-center justify-between">
              <span>{t("walkthrough.slide_4_gates_title")}</span>
              <span className="text-[10px] text-text-3 font-normal">§8.3 Econometric Standard</span>
            </div>
            <div className="grid grid-cols-2 gap-2 text-[11px] text-text-3">
              <div>• {t("research.gate_1_title")}</div>
              <div>• {t("research.gate_2_title")}</div>
              <div>• {t("research.gate_3_title")}</div>
              <div>• {t("research.gate_4_title")}</div>
              <div>• {t("research.gate_5_title")}</div>
              <div>• {t("research.gate_6_title")}</div>
              <div>• {t("research.gate_7_title")}</div>
              <div>• {t("research.gate_8_title")}</div>
            </div>
          </div>
          <div className="p-2.5 bg-warn/10 border border-warn/30 rounded text-[11px] font-mono text-warn flex items-center justify-between">
            <span>{t("walkthrough.slide_4_holdout_note")}</span>
            <Link
              href="/research"
              onClick={onClose}
              className="text-warn hover:underline font-bold"
            >
              {t("nav.research")} &rarr;
            </Link>
          </div>
        </div>
      ),
    },
    {
      id: "live_risk",
      icon: Radio,
      badge: "EXECUTION & RISK",
      title: t("walkthrough.slide_5_title"),
      subtitle: t("walkthrough.slide_5_subtitle"),
      content: (
        <div className="space-y-4">
          <p className="text-xs text-text-2 leading-relaxed">
            {t("walkthrough.slide_5_desc")}
          </p>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3 text-xs font-mono">
            <div className="p-3 bg-surface-2 border border-border rounded space-y-1">
              <div className="text-text-1 font-bold flex items-center gap-1.5">
                <Zap className="w-3.5 h-3.5 text-pos" />
                {t("walkthrough.slide_5_execution_title")}
              </div>
              <p className="text-text-3 text-[11px] leading-relaxed">
                {t("walkthrough.slide_5_execution_desc")}
              </p>
            </div>
            <div className="p-3 bg-surface-2 border border-border rounded space-y-1">
              <div className="text-text-1 font-bold flex items-center gap-1.5">
                <ShieldAlert className="w-3.5 h-3.5 text-neg" />
                {t("walkthrough.slide_5_killswitch_title")}
              </div>
              <p className="text-text-3 text-[11px] leading-relaxed">
                {t("walkthrough.slide_5_killswitch_desc")}
              </p>
            </div>
          </div>
          <div className="p-2.5 bg-active border border-border-subtle rounded text-[11px] font-mono text-text-2 flex items-center justify-between">
            <span>{t("walkthrough.slide_5_live_tip")}</span>
            <Link
              href="/live"
              onClick={onClose}
              className="text-pos hover:underline text-[11px] font-bold"
            >
              {t("nav.live")} &rarr;
            </Link>
          </div>
        </div>
      ),
    },
    {
      id: "playbook",
      icon: Sparkles,
      badge: "USER PLAYBOOK",
      title: t("walkthrough.slide_6_title"),
      subtitle: t("walkthrough.slide_6_subtitle"),
      content: (
        <div className="space-y-4">
          <p className="text-xs text-text-2 leading-relaxed">
            {t("walkthrough.slide_6_desc")}
          </p>
          <div className="space-y-2 text-xs font-mono">
            <div className="p-2.5 bg-surface-2 border border-border rounded flex items-center justify-between">
              <div>
                <span className="text-pos font-bold">1. {t("walkthrough.slide_6_step1_title")}: </span>
                <span className="text-text-3 text-[11px]">{t("walkthrough.slide_6_step1_desc")}</span>
              </div>
              <Link href="/models" onClick={onClose} className="text-pos hover:underline text-[10px] shrink-0 ml-2">
                /models &rarr;
              </Link>
            </div>
            <div className="p-2.5 bg-surface-2 border border-border rounded flex items-center justify-between">
              <div>
                <span className="text-info font-bold">2. {t("walkthrough.slide_6_step2_title")}: </span>
                <span className="text-text-3 text-[11px]">{t("walkthrough.slide_6_step2_desc")}</span>
              </div>
              <Link href="/fundamentals" onClick={onClose} className="text-info hover:underline text-[10px] shrink-0 ml-2">
                /fundamentals &rarr;
              </Link>
            </div>
            <div className="p-2.5 bg-surface-2 border border-border rounded flex items-center justify-between">
              <div>
                <span className="text-warn font-bold">3. {t("walkthrough.slide_6_step3_title")}: </span>
                <span className="text-text-3 text-[11px]">{t("walkthrough.slide_6_step3_desc")}</span>
              </div>
              <Link href="/research" onClick={onClose} className="text-warn hover:underline text-[10px] shrink-0 ml-2">
                /research &rarr;
              </Link>
            </div>
            <div className="p-2.5 bg-surface-2 border border-border rounded flex items-center justify-between">
              <div>
                <span className="text-pos font-bold">4. {t("walkthrough.slide_6_step4_title")}: </span>
                <span className="text-text-3 text-[11px]">{t("walkthrough.slide_6_step4_desc")}</span>
              </div>
              <Link href="/live" onClick={onClose} className="text-pos hover:underline text-[10px] shrink-0 ml-2">
                /live &rarr;
              </Link>
            </div>
          </div>
        </div>
      ),
    },
  ];

  const currentSlide = slides[step];
  const Icon = currentSlide.icon;

  return (
    <div className="fixed inset-0 bg-black/80 backdrop-blur-sm flex items-center justify-center z-50 p-4 font-mono">
      <div className="bg-surface border border-border rounded-lg max-w-2xl w-full shadow-2xl flex flex-col max-h-[90vh] overflow-hidden animate-in fade-in zoom-in-95 duration-200">
        {/* Top Header */}
        <div className="flex items-center justify-between border-b border-border p-4 bg-surface-2">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded bg-surface border border-border flex items-center justify-center text-pos">
              <Icon className="w-4 h-4" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <span className="text-[10px] font-bold px-2 py-0.5 rounded bg-pos/10 border border-pos/30 text-pos">
                  {currentSlide.badge}
                </span>
                <span className="text-xs text-text-3 font-mono">
                  {t("walkthrough.step_indicator")} {step + 1} / {totalSteps}
                </span>
              </div>
              <h2 className="text-sm font-bold text-text-1 mt-0.5">
                {currentSlide.title}
              </h2>
            </div>
          </div>

          <div className="flex items-center gap-2">
            <Link
              href="/docs"
              onClick={onClose}
              className="flex items-center gap-1.5 px-2.5 py-1 rounded bg-surface border border-border text-[11px] text-text-3 hover:text-text-1 hover:border-pos transition-colors"
            >
              <BookOpen className="w-3.5 h-3.5 text-pos" />
              <span>{t("walkthrough.open_full_docs")}</span>
            </Link>
            <button
              onClick={onClose}
              className="p-1 rounded text-text-3 hover:text-text-1 hover:bg-surface transition-colors"
            >
              <X className="w-4 h-4" />
            </button>
          </div>
        </div>

        {/* Slide Body */}
        <div className="p-6 overflow-y-auto space-y-4">
          <div className="text-xs font-bold text-text-3 uppercase tracking-wider">
            {currentSlide.subtitle}
          </div>
          {currentSlide.content}
        </div>

        {/* Footer Navigation */}
        <div className="flex items-center justify-between border-t border-border p-4 bg-surface-2">
          {/* Dot Indicators */}
          <div className="flex items-center gap-1.5">
            {slides.map((_, i) => (
              <button
                key={i}
                onClick={() => setStep(i)}
                className={`h-2 rounded-full transition-all ${
                  step === i
                    ? "w-6 bg-pos"
                    : "w-2 bg-surface border border-border hover:bg-text-3"
                }`}
                title={`Go to step ${i + 1}`}
              />
            ))}
          </div>

          {/* Action Buttons */}
          <div className="flex items-center gap-2">
            <button
              onClick={() => setStep((s) => Math.max(s - 1, 0))}
              disabled={step === 0}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded border border-border text-xs text-text-2 hover:text-text-1 hover:border-text-3 disabled:opacity-30 disabled:pointer-events-none transition-all"
            >
              <ArrowLeft className="w-3.5 h-3.5" />
              <span>{t("walkthrough.btn_prev")}</span>
            </button>

            {step < totalSteps - 1 ? (
              <button
                onClick={() => setStep((s) => Math.min(s + 1, totalSteps - 1))}
                className="flex items-center gap-1.5 px-3.5 py-1.5 rounded bg-pos text-bg text-xs font-bold hover:bg-pos/90 transition-all"
              >
                <span>{t("walkthrough.btn_next")}</span>
                <ArrowRight className="w-3.5 h-3.5" />
              </button>
            ) : (
              <button
                onClick={onClose}
                className="flex items-center gap-1.5 px-3.5 py-1.5 rounded bg-pos text-bg text-xs font-bold hover:bg-pos/90 transition-all"
              >
                <span>{t("walkthrough.btn_finish")}</span>
                <CheckCircle2 className="w-3.5 h-3.5" />
              </button>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
