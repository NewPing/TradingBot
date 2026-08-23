"use client";

import React, { createContext, useContext, useEffect, useState, useMemo } from "react";
import { Locale, TranslationDictionary } from "./types";
import { en } from "./en";
import { de } from "./de";

interface LanguageContextType {
  locale: Locale;
  setLocale: (locale: Locale) => void;
  t: (key: string, fallback?: string, params?: Record<string, string | number>) => string;
  dict: TranslationDictionary;
}

const dictionaries: Record<Locale, TranslationDictionary> = {
  en,
  de,
};

const LanguageContext = createContext<LanguageContextType | null>(null);

const STORAGE_KEY = "atlas_locale";

export function LanguageProvider({ children }: { children: React.ReactNode }) {
  const [locale, setLocaleState] = useState<Locale>("en");
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setMounted(true);
    try {
      const saved = localStorage.getItem(STORAGE_KEY) as Locale | null;
      if (saved && (saved === "en" || saved === "de")) {
        setLocaleState(saved);
        document.documentElement.lang = saved;
      } else {
        document.documentElement.lang = "en";
      }
    } catch {
      // Ignore localStorage errors in restricted environments
    }
  }, []);

  const setLocale = (newLocale: Locale) => {
    setLocaleState(newLocale);
    try {
      localStorage.setItem(STORAGE_KEY, newLocale);
      document.documentElement.lang = newLocale;
    } catch {
      // Ignore
    }
  };

  const currentDict = dictionaries[locale] || en;

  const t = useMemo(() => {
    return (key: string, fallback?: string, params?: Record<string, string | number>): string => {
      const parts = key.split(".");
      let current: any = currentDict;

      for (const part of parts) {
        if (current && typeof current === "object" && part in current) {
          current = current[part];
        } else {
          current = undefined;
          break;
        }
      }

      if (typeof current !== "string") {
        // Fallback to English dictionary if missing in active language
        let enCurrent: any = en;
        for (const part of parts) {
          if (enCurrent && typeof enCurrent === "object" && part in enCurrent) {
            enCurrent = enCurrent[part];
          } else {
            enCurrent = undefined;
            break;
          }
        }
        current = typeof enCurrent === "string" ? enCurrent : (fallback || key);
      }

      let result = current as string;
      if (params) {
        Object.entries(params).forEach(([paramKey, paramVal]) => {
          result = result.replace(new RegExp(`\\{${paramKey}\\}`, "g"), String(paramVal));
        });
      }

      return result;
    };
  }, [currentDict]);

  return (
    <LanguageContext.Provider value={{ locale, setLocale, t, dict: currentDict }}>
      {children}
    </LanguageContext.Provider>
  );
}

export function useTranslation() {
  const context = useContext(LanguageContext);
  if (!context) {
    // Return default English context if rendered outside provider
    return {
      locale: "en" as Locale,
      setLocale: () => {},
      t: (key: string, fallback?: string) => fallback || key,
      dict: en,
    };
  }
  return context;
}
