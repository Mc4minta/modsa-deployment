import { useEffect, useRef } from "react";
import { useLanguage } from "../i18n/LanguageContext";
import LanguageSwitcher from "./LanguageSwitcher";
import logoSvg from "../assets/logo.svg";
import type { ChatListItem } from "../types";

function groupChatsByDate(chatList: ChatListItem[]) {
  const now = new Date();
  const today = new Date(now.getFullYear(), now.getMonth(), now.getDate()).getTime();
  const yesterday = today - 86400000;
  const groups: { today: ChatListItem[]; yesterday: ChatListItem[]; older: ChatListItem[] } = {
    today: [],
    yesterday: [],
    older: [],
  };
  chatList.forEach((chat) => {
    if (chat.updatedAt >= today) groups.today.push(chat);
    else if (chat.updatedAt >= yesterday) groups.yesterday.push(chat);
    else groups.older.push(chat);
  });
  return groups;
}

interface SidebarProps {
  isOpen: boolean;
  onToggle: () => void;
  chatList: ChatListItem[];
  loadingChatIds: string[];
  unseenChatIds: string[];
  activeSessionId: string;
  onNewChat: () => void;
  onSelectChat: (chatId: string) => void;
  onDeleteChat: (chatId: string) => void;
  onClearHistory: () => void;
}

export default function Sidebar({
  isOpen,
  onToggle,
  chatList,
  loadingChatIds,
  unseenChatIds,
  activeSessionId,
  onNewChat,
  onSelectChat,
  onDeleteChat,
  onClearHistory,
}: SidebarProps) {
  const { t } = useLanguage();
  const sidebarRef = useRef<HTMLElement>(null);
  const closeButtonRef = useRef<HTMLButtonElement>(null);
  const newChatButtonRef = useRef<HTMLButtonElement>(null);
  const previousFocusRef = useRef<HTMLElement | null>(null);
  const wasOpenRef = useRef(false);

  const isMobileViewport = () =>
    typeof window !== "undefined" && window.matchMedia?.("(max-width: 768px)").matches;

  useEffect(() => {
    if (!isMobileViewport()) return undefined;

    if (isOpen) {
      previousFocusRef.current = document.activeElement as HTMLElement | null;
      wasOpenRef.current = true;
      const focusInitialControl = () => {
        if (!wasOpenRef.current) return;
        if (closeButtonRef.current && closeButtonRef.current.offsetParent !== null) {
          closeButtonRef.current.focus();
        } else {
          newChatButtonRef.current?.focus();
        }
      };
      if (typeof window.requestAnimationFrame === "function") window.requestAnimationFrame(focusInitialControl);
      else focusInitialControl();
      return undefined;
    }

    if (wasOpenRef.current) {
      const target = previousFocusRef.current;
      if (target?.isConnected && typeof target.focus === "function") target.focus();
      wasOpenRef.current = false;
    }
    return undefined;
  }, [isOpen]);

  useEffect(() => {
    if (!isOpen) return undefined;

    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape" && isMobileViewport()) {
        event.preventDefault();
        onToggle();
        return;
      }
      if (event.key !== "Tab" || !sidebarRef.current || !isMobileViewport()) return;

      const focusable = Array.from(
        sidebarRef.current.querySelectorAll<HTMLElement>(
          'button:not([disabled]), [href], input:not([disabled]), textarea:not([disabled]), select:not([disabled]), [tabindex]:not([tabindex="-1"])'
        )
      ).filter((element) => element.offsetParent !== null);
      if (focusable.length === 0) return;
      const first = focusable[0];
      const last = focusable[focusable.length - 1];
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first.focus();
      }
    };

    document.addEventListener("keydown", handleKeyDown);
    return () => document.removeEventListener("keydown", handleKeyDown);
  }, [isOpen, onToggle]);

  const groups = groupChatsByDate(chatList);
  const loadingSet = new Set(loadingChatIds);
  const unseenSet = new Set(unseenChatIds);

  const renderGroup = (groupKey: string, label: string, chats: ChatListItem[]) => {
    if (chats.length === 0) return null;
    const groupId = `history-group-${groupKey}`;
    return (
      <div className="history-group" key={groupKey} role="group" aria-labelledby={groupId}>
        <div className="history-group-label" id={groupId}>{label}</div>
        {chats.map((chat) => (
          <div
            key={chat.id}
            className={`history-item ${chat.id === activeSessionId ? "active" : ""}`}
            id={`history-${chat.id}`}
            role="listitem"
          >
            <button
              type="button"
              className="history-item-select"
              onClick={() => onSelectChat(chat.id)}
              aria-current={chat.id === activeSessionId ? "true" : undefined}
              aria-controls="chat-panel"
              aria-label={chat.title}
            >
              <span className="history-item-content">
                <span className="history-title">{chat.title}</span>
                <span className="history-preview">{chat.preview}</span>
              </span>
            </button>
            {loadingSet.has(chat.id) ? (
              <span className="history-item-spinner" aria-label={t("loading")} title={t("loading")} />
            ) : (
              unseenSet.has(chat.id) && (
                <span className="history-item-unseen-dot" aria-label={t("newResponse")} title={t("newResponse")} />
              )
            )}
            <button
              type="button"
              className="history-delete"
              onClick={() => onDeleteChat(chat.id)}
              aria-label={`${t("deleteChat")}: ${chat.title}`}
              title={t("deleteChat")}
            >
              <svg width="14" height="14" viewBox="0 0 14 14" fill="none" aria-hidden="true">
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
      <button
        type="button"
        className={`sidebar-overlay ${isOpen ? "visible" : ""}`}
        onClick={onToggle}
        aria-label={t("close")}
        tabIndex={isOpen ? 0 : -1}
      />
      <aside
        ref={sidebarRef}
        className={`sidebar ${isOpen ? "open" : ""}`}
        id="sidebar"
        aria-label={t("chatHistory")}
      >
        <div className="sidebar-header">
          <div className="sidebar-brand">
            <img src={logoSvg} alt="MOD-SA" className="sidebar-logo" />
            <div className="sidebar-brand-text">
              <span className="sidebar-app-name">{t("appName")}</span>
              <span className="sidebar-tagline">{t("appTagline")}</span>
            </div>
          </div>
          <button
            ref={closeButtonRef}
            type="button"
            className="sidebar-close"
            onClick={onToggle}
            id="sidebar-close"
            aria-label={t("close")}
            title={t("close")}
          >
            <svg width="20" height="20" viewBox="0 0 20 20" fill="none" aria-hidden="true">
              <path d="M13 4L7 10L13 16" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
            </svg>
          </button>
        </div>

        <button ref={newChatButtonRef} type="button" className="new-chat-btn" onClick={onNewChat} id="btn-new-chat">
          <svg width="18" height="18" viewBox="0 0 18 18" fill="none" aria-hidden="true">
            <path d="M9 3V15M3 9H15" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
          </svg>
          {t("newChat")}
        </button>

        <div className="sidebar-section">
          <div className="sidebar-section-title">{t("chatHistory")}</div>
          <div className="history-list" id="history-list" role="list">
            {chatList.length === 0 ? (
              <div className="history-empty">{t("noHistory")}</div>
            ) : (
              <>
                {renderGroup("today", t("today"), groups.today)}
                {renderGroup("yesterday", t("yesterday"), groups.yesterday)}
                {renderGroup("older", t("older"), groups.older)}
              </>
            )}
          </div>
        </div>

        <div className="sidebar-footer">
          <LanguageSwitcher />
          {chatList.length > 0 && (
            <button
              type="button"
              className="clear-history-btn"
              onClick={onClearHistory}
              id="clear-history-btn"
            >
              {t("clearHistory")}
            </button>
          )}
          <div className="sidebar-powered">{t("poweredBy")}</div>
        </div>
      </aside>
    </>
  );
}
