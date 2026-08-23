"use client";

import { useTranslation } from "@/i18n";
import { Globe } from "lucide-react";

export function LanguageSwitch() {
  const { locale, setLocale } = useTranslation();

  return (
    <div className="flex items-center justify-between bg-surface border border-border rounded p-1.5 text-xs font-mono">
      <div className="flex items-center gap-1.5 text-text-3 pl-1">
        <Globe className="w-3.5 h-3.5 text-text-3" />
        <span className="text-[10px] tracking-wider uppercase font-semibold">LANG</span>
      </div>

      <div className="flex items-center gap-1 bg-surface-2 p-0.5 rounded border border-border">
        <button
          type="button"
          onClick={() => setLocale("en")}
          className={`px-2 py-0.5 rounded text-[10px] font-bold transition-all ${
            locale === "en"
              ? "bg-pos text-bg shadow-sm"
              : "text-text-3 hover:text-text-1"
          }`}
          title="English"
        >
          EN
        </button>
        <button
          type="button"
          onClick={() => setLocale("de")}
          className={`px-2 py-0.5 rounded text-[10px] font-bold transition-all ${
            locale === "de"
              ? "bg-pos text-bg shadow-sm"
              : "text-text-3 hover:text-text-1"
          }`}
          title="Deutsch"
        >
          DE
        </button>
      </div>
    </div>
  );
}
