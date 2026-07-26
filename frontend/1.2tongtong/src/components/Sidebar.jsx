import { useEffect, useMemo, useRef, useState } from "react";
import { useLanguage } from "../i18n/useLanguage";
import logoSvg from "../assets/logo.svg";
import { Icon } from "./Icon";
import { LanguageSwitcher } from "./LanguageSwitcher";

function groupChats(chatList) {
  const now = new Date();
  const today = new Date(now.getFullYear(), now.getMonth(), now.getDate()).getTime();
  const yesterday = today - 86_400_000;
  const groups = { today: [], yesterday: [], older: [] };

  chatList.forEach((chat) => {
    if (chat.updatedAt >= today) groups.today.push(chat);
    else if (chat.updatedAt >= yesterday) groups.yesterday.push(chat);
    else groups.older.push(chat);
  });
  return groups;
}

export function Sidebar({
  isOpen,
  onToggle,
  chatList,
  activeSessionId,
  onNewChat,
  onSelectChat,
  onDeleteChat,
  onClearHistory,
}) {
  const { t } = useLanguage();
  const closeButtonRef = useRef(null);
  const [isMobile, setIsMobile] = useState(
    () => window.matchMedia?.("(max-width: 900px)").matches ?? false,
  );
  const groups = useMemo(() => groupChats(chatList), [chatList]);
  const isHidden = isMobile && !isOpen;

  useEffect(() => {
    const media = window.matchMedia?.("(max-width: 900px)");
    if (!media) return undefined;
    const handleChange = (event) => setIsMobile(event.matches);
    media.addEventListener("change", handleChange);
    return () => media.removeEventListener("change", handleChange);
  }, []);

  useEffect(() => {
    if (!isOpen || !isMobile) return undefined;
    closeButtonRef.current?.focus();
    const handleKeyDown = (event) => {
      if (event.key === "Escape") onToggle();
    };
    document.addEventListener("keydown", handleKeyDown);
    return () => document.removeEventListener("keydown", handleKeyDown);
  }, [isMobile, isOpen, onToggle]);

  const renderGroup = (key, chats) => {
    if (chats.length === 0) return null;
    return (
      <section className="history-group" key={key} aria-labelledby={`history-${key}`}>
        <h2 id={`history-${key}`} className="history-group-label">
          {t(key)}
        </h2>
        {chats.map((chat) => (
          <div
            key={chat.id}
            className={`history-item ${chat.id === activeSessionId ? "active" : ""}`}
          >
            <button
              className="history-select"
              onClick={() => onSelectChat(chat.id)}
              type="button"
              aria-current={chat.id === activeSessionId ? "true" : undefined}
            >
              <span className="history-title">{chat.title}</span>
            </button>
            <button
              className="history-delete"
              onClick={() => onDeleteChat(chat.id)}
              title={t("deleteChat")}
              type="button"
            >
              <Icon name="trash" size={16} />
              <span className="sr-only">{t("deleteChat")}</span>
            </button>
          </div>
        ))}
      </section>
    );
  };

  return (
    <>
      <button
        className={`sidebar-overlay ${isOpen ? "visible" : ""}`}
        onClick={onToggle}
        type="button"
        aria-label={t("closeMenu")}
        aria-hidden={!isOpen}
        disabled={!isOpen}
        tabIndex={isOpen ? 0 : -1}
      />
      <aside
        className={`sidebar ${isOpen ? "open" : ""}`}
        aria-label={t("chatHistory")}
        aria-hidden={isHidden}
        inert={isHidden}
      >
        <div className="sidebar-header">
          <div className="sidebar-brand">
            <span className="sidebar-logo-shell">
              <img src={logoSvg} alt="" className="sidebar-logo" />
            </span>
            <div>
              <strong>{t("appName")}</strong>
              <span>KMUTT Student Affairs</span>
            </div>
          </div>
          <button
            ref={closeButtonRef}
            className="sidebar-close"
            onClick={onToggle}
            type="button"
            aria-label={t("closeMenu")}
          >
            <Icon name="close" />
          </button>
        </div>

        <button className="new-chat-button" onClick={onNewChat} type="button">
          <Icon name="plus" size={18} />
          {t("newChat")}
        </button>

        <div className="history-header">
          <h2>{t("chatHistory")}</h2>
          {chatList.length > 0 && (
            <button
              className="text-button"
              onClick={() => {
                if (window.confirm(t("clearHistoryConfirm"))) onClearHistory();
              }}
              type="button"
            >
              {t("clearHistory")}
            </button>
          )}
        </div>

        <div className="history-list">
          {chatList.length === 0 ? (
            <p className="history-empty">{t("noHistory")}</p>
          ) : (
            <>
              {renderGroup("today", groups.today)}
              {renderGroup("yesterday", groups.yesterday)}
              {renderGroup("older", groups.older)}
            </>
          )}
        </div>

        <div className="sidebar-footer">
          <LanguageSwitcher />
          <p>{t("localHistoryNotice")}</p>
          <small>{t("poweredBy")}</small>
        </div>
      </aside>
    </>
  );
}
