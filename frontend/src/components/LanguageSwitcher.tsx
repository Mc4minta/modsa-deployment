import { useLanguage } from "../i18n/LanguageContext";

export default function LanguageSwitcher() {
  const { lang, switchLanguage, t } = useLanguage();

  return (
    <div className="language-switcher" id="language-switcher" role="group" aria-label={t("language")}>
      <button
        type="button"
        className={`lang-btn ${lang === "en" ? "active" : ""}`}
        onClick={() => switchLanguage("en")}
        aria-label="Switch to English"
        aria-pressed={lang === "en"}
        id="lang-btn-en"
      >
        EN
      </button>
      <button
        type="button"
        className={`lang-btn ${lang === "th" ? "active" : ""}`}
        onClick={() => switchLanguage("th")}
        aria-label="Switch to Thai"
        aria-pressed={lang === "th"}
        id="lang-btn-th"
      >
        TH
      </button>
    </div>
  );
}
