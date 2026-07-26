import { useLanguage } from "../i18n/useLanguage";

export function LanguageSwitcher() {
  const { lang, switchLanguage } = useLanguage();

  return (
    <div className="language-switcher" role="group" aria-label="Language">
      <button
        className={lang === "en" ? "active" : ""}
        onClick={() => switchLanguage("en")}
        type="button"
        aria-pressed={lang === "en"}
      >
        EN
      </button>
      <button
        className={lang === "th" ? "active" : ""}
        onClick={() => switchLanguage("th")}
        type="button"
        aria-pressed={lang === "th"}
      >
        ไทย
      </button>
    </div>
  );
}
