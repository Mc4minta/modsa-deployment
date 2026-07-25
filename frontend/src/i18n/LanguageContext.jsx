import { createContext, useContext, useState, useCallback } from "react";
import locales from "./locales";

const LanguageContext = createContext();

export function LanguageProvider({ children }) {
  const [lang, setLang] = useState(() => {
    try {
      return localStorage.getItem("modsa-lang") || "en";
    } catch {
      return "en";
    }
  });

  const switchLanguage = useCallback((newLang) => {
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
