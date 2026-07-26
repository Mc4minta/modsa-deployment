import { useCallback, useEffect, useMemo, useState } from "react";
import locales from "./locales";
import { LanguageContext } from "./language-context";

export function LanguageProvider({ children }) {
  const [lang, setLang] = useState(() => {
    try {
      const saved = localStorage.getItem("modsa-lang");
      if (saved === "en" || saved === "th") return saved;
      return navigator.language?.toLowerCase().startsWith("th") ? "th" : "en";
    } catch {
      return "en";
    }
  });

  useEffect(() => {
    document.documentElement.lang = lang;
  }, [lang]);

  const switchLanguage = useCallback((newLang) => {
    if (newLang !== "en" && newLang !== "th") return;
    setLang(newLang);
    try {
      localStorage.setItem("modsa-lang", newLang);
    } catch {
      // Language persistence is optional.
    }
  }, []);

  const t = useCallback(
    (key) => locales[lang]?.[key] || locales.en?.[key] || key,
    [lang],
  );

  const value = useMemo(
    () => ({ lang, switchLanguage, t }),
    [lang, switchLanguage, t],
  );

  return <LanguageContext.Provider value={value}>{children}</LanguageContext.Provider>;
}
