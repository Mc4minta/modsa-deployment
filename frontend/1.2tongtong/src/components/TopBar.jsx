import { useLanguage } from "../i18n/useLanguage";
import { Icon } from "./Icon";

export function TopBar({ healthStatus, onRefreshHealth, onOpenMenu, onNewChat }) {
  const { t } = useLanguage();
  const statusLabel = t(
    healthStatus === "online"
      ? "online"
      : healthStatus === "offline"
        ? "offline"
        : "checking",
  );

  return (
    <header className="top-bar">
      <button
        className="menu-button"
        onClick={onOpenMenu}
        type="button"
        aria-label={t("openMenu")}
      >
        <Icon name="menu" />
      </button>

      <div className="top-bar-title">
        <strong>{t("appName")}</strong>
        <span>Student Affairs</span>
      </div>

      <div className="top-bar-actions">
        <button
          className={`health-status health-${healthStatus}`}
          onClick={onRefreshHealth}
          type="button"
          title={t("retryConnection")}
          aria-label={`${statusLabel}. ${t("retryConnection")}`}
        >
          <span className="status-dot" aria-hidden="true" />
          <span className="health-label">{statusLabel}</span>
        </button>
        <button
          className="top-new-chat"
          onClick={onNewChat}
          type="button"
          aria-label={t("newChat")}
        >
          <Icon name="plus" size={18} />
          <span>{t("newChat")}</span>
        </button>
      </div>
    </header>
  );
}
