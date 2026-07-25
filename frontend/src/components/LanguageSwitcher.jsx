import { useLanguage } from "../i18n/LanguageContext";

export default function LanguageSwitcher() {
  const { lang, switchLanguage } = useLanguage();

  return (
    <div className="language-switcher" id="language-switcher">
      <button
        className={`lang-btn ${lang === "en" ? "active" : ""}`}
        onClick={() => switchLanguage("en")}
        aria-label="Switch to English"
        id="lang-btn-en"
      >
        EN
      </button>
      <button
        className={`lang-btn ${lang === "th" ? "active" : ""}`}
        onClick={() => switchLanguage("th")}
        aria-label="เปลี่ยนเป็นภาษาไทย"
        id="lang-btn-th"
      >
        TH
      </button>
    </div>
  );
}
