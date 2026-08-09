import { useLanguage } from "../i18n/LanguageContext";
import LanguageSwitcher from "./LanguageSwitcher";
import logoSvg from "../assets/logo.svg";

export default function Sidebar({
  isOpen,
  onToggle,
  chatList,
  activeSessionId,
  onNewChat,
  onSelectChat,
  onDeleteChat,
}) {
  const { t } = useLanguage();

  const groupChats = () => {
    const now = new Date();
    const today = new Date(now.getFullYear(), now.getMonth(), now.getDate()).getTime();
    const yesterday = today - 86400000;
    const groups = { today: [], yesterday: [], older: [] };
    chatList.forEach((chat) => {
      if (chat.updatedAt >= today) groups.today.push(chat);
      else if (chat.updatedAt >= yesterday) groups.yesterday.push(chat);
      else groups.older.push(chat);
    });
    return groups;
  };

  const groups = groupChats();

  const renderGroup = (label, chats) => {
    if (chats.length === 0) return null;
    return (
      <div className="history-group" key={label}>
        <div className="history-group-label">{label}</div>
        {chats.map((chat) => (
          <div
            key={chat.id}
            className={`history-item ${chat.id === activeSessionId ? "active" : ""}`}
            onClick={() => onSelectChat(chat.id)}
            id={`history-${chat.id}`}
          >
            <div className="history-item-content">
              <span className="history-title">{chat.title}</span>
              <span className="history-preview">{chat.preview}</span>
            </div>
            <button
              className="history-delete"
              onClick={(e) => { e.stopPropagation(); onDeleteChat(chat.id); }}
              title={t("deleteChat")}
            >
              <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
                <path d="M3 4H11L10.3 12H3.7L3 4Z" stroke="currentColor" strokeWidth="1.1" strokeLinejoin="round" />
                <path d="M5.5 6.5V9.5M8.5 6.5V9.5" stroke="currentColor" strokeWidth="1.1" strokeLinecap="round" />
                <path d="M2 4H12M5 4V2.5H9V4" stroke="currentColor" strokeWidth="1.1" strokeLinecap="round" strokeLinejoin="round" />
              </svg>
            </button>
          </div>
        ))}
      </div>
    );
  };

  return (
    <>
      <div className={`sidebar-overlay ${isOpen ? "visible" : ""}`} onClick={onToggle}></div>
      <aside className={`sidebar ${isOpen ? "open" : ""}`} id="sidebar">
        <div className="sidebar-header">
          <div className="sidebar-brand">
            <img src={logoSvg} alt="MOD-SA" className="sidebar-logo" />
            <div className="sidebar-brand-text">
              <span className="sidebar-app-name">{t("appName")}</span>
              <span className="sidebar-tagline">{t("appTagline")}</span>
            </div>
          </div>
          <button className="sidebar-close" onClick={onToggle} id="sidebar-close">
            <svg width="20" height="20" viewBox="0 0 20 20" fill="none">
              <path d="M13 4L7 10L13 16" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
            </svg>
          </button>
        </div>

        <button className="new-chat-btn" onClick={onNewChat} id="btn-new-chat">
          <svg width="18" height="18" viewBox="0 0 18 18" fill="none">
            <path d="M9 3V15M3 9H15" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
          </svg>
          {t("newChat")}
        </button>

        <div className="sidebar-section">
          <div className="sidebar-section-title">{t("chatHistory")}</div>
          <div className="history-list" id="history-list">
            {chatList.length === 0 ? (
              <div className="history-empty">{t("noHistory")}</div>
            ) : (
              <>
                {renderGroup(t("today"), groups.today)}
                {renderGroup(t("yesterday"), groups.yesterday)}
                {renderGroup(t("older"), groups.older)}
              </>
            )}
          </div>
        </div>

        <div className="sidebar-footer">
          <LanguageSwitcher />
          <div className="sidebar-powered">{t("poweredBy")}</div>
        </div>
      </aside>
    </>
  );
}
