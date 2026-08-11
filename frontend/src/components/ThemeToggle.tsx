import { useTheme } from "../theme/ThemeContext";
import { useLanguage } from "../i18n/LanguageContext";

export default function ThemeToggle() {
  const { theme, toggleTheme } = useTheme();
  const { t } = useLanguage();
  const isDark = theme === "dark";

  return (
    <button
      type="button"
      className="theme-toggle"
      id="theme-toggle"
      onClick={toggleTheme}
      aria-label={isDark ? t("switchToLight") : t("switchToDark")}
      title={isDark ? t("switchToLight") : t("switchToDark")}
      aria-pressed={isDark}
    >
      {isDark ? (
        <svg width="18" height="18" viewBox="0 0 18 18" fill="none" aria-hidden="true">
          <circle cx="9" cy="9" r="4" stroke="currentColor" strokeWidth="1.5" />
          <path
            d="M9 1.5V3M9 15V16.5M16.5 9H15M3 9H1.5M14.3 3.7L13.2 4.8M4.8 13.2L3.7 14.3M14.3 14.3L13.2 13.2M4.8 4.8L3.7 3.7"
            stroke="currentColor"
            strokeWidth="1.5"
            strokeLinecap="round"
          />
        </svg>
      ) : (
        <svg width="18" height="18" viewBox="0 0 18 18" fill="none" aria-hidden="true">
          <path
            d="M15.5 10.5A6.5 6.5 0 1 1 7.5 2.5a5.2 5.2 0 0 0 8 8Z"
            stroke="currentColor"
            strokeWidth="1.5"
            strokeLinejoin="round"
          />
        </svg>
      )}
    </button>
  );
}
