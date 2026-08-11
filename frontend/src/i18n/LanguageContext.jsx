import { createContext, useContext, useEffect, useState, useCallback } from "react";
import locales from "./locales";

const LanguageContext = createContext();
const SUPPORTED_LANGUAGES = new Set(["en", "th"]);

function readStoredLanguage() {
  try {
    const storedLanguage = localStorage.getItem("modsa-lang");
    return SUPPORTED_LANGUAGES.has(storedLanguage) ? storedLanguage : "en";
  } catch {
    return "en";
  }
}

export function LanguageProvider({ children }) {
  const [lang, setLang] = useState(readStoredLanguage);

  useEffect(() => {
    if (typeof document !== "undefined") document.documentElement.lang = lang;
  }, [lang]);

  const switchLanguage = useCallback((newLang) => {
    if (!SUPPORTED_LANGUAGES.has(newLang)) return;
    setLang(newLang);
    try {
      localStorage.setItem("modsa-lang", newLang);
    } catch {
      /* ignore */
    }
  }, []);

  const t = useCallback(
    (key) => {
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

export function useLanguage() {
  const ctx = useContext(LanguageContext);
  if (!ctx) throw new Error("useLanguage must be used within LanguageProvider");
  return ctx;
}
