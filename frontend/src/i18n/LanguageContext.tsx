import { createContext, useContext, useEffect, useState, useCallback, type ReactNode } from "react";
import locales, { type Lang } from "./locales";

interface LanguageContextValue {
  lang: Lang;
  switchLanguage: (newLang: Lang) => void;
  t: (key: string) => string;
}

const LanguageContext = createContext<LanguageContextValue | undefined>(undefined);
const SUPPORTED_LANGUAGES = new Set<Lang>(["en", "th"]);

function isSupportedLang(value: string | null): value is Lang {
  return value !== null && SUPPORTED_LANGUAGES.has(value as Lang);
}

function readStoredLanguage(): Lang {
  try {
    const storedLanguage = localStorage.getItem("modsa-lang");
    return isSupportedLang(storedLanguage) ? storedLanguage : "en";
  } catch {
    return "en";
  }
}

export function LanguageProvider({ children }: { children: ReactNode }) {
  const [lang, setLang] = useState<Lang>(readStoredLanguage);

  useEffect(() => {
    if (typeof document !== "undefined") document.documentElement.lang = lang;
  }, [lang]);

  const switchLanguage = useCallback((newLang: Lang) => {
    if (!SUPPORTED_LANGUAGES.has(newLang)) return;
    setLang(newLang);
    try {
      localStorage.setItem("modsa-lang", newLang);
    } catch {
      /* ignore */
    }
  }, []);

  const t = useCallback(
    (key: string) => {
      return locales[lang]?.[key] || locales.en?.[key] || key;
    },
    [lang]
  );

  return (
    <LanguageContext.Provider value={{ lang, switchLanguage, t }}>
      {children}
    </LanguageContext.Provider>
  );
}

export function useLanguage(): LanguageContextValue {
  const ctx = useContext(LanguageContext);
  if (!ctx) throw new Error("useLanguage must be used within LanguageProvider");
  return ctx;
}
