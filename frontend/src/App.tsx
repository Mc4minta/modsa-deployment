import { useState, useCallback, useEffect } from "react";
import { useLanguage } from "./i18n/LanguageContext";
import Sidebar from "./components/Sidebar";
import ChatPanel from "./components/ChatPanel";
import InputArea from "./components/InputArea";
import { useChatController } from "./hooks/useChatController";
import "./App.css";

function readInitialSidebarOpen(): boolean {
  const isDesktop = typeof window !== "undefined" && window.matchMedia?.("(min-width: 769px)").matches;
  if (!isDesktop) return false;
  try {
    const stored = localStorage.getItem("modsa-sidebar-open");
    return stored === null ? true : stored === "true";
  } catch {
    return true;
  }
}

export default function App() {
  const { t } = useLanguage();
  const [sidebarOpen, setSidebarOpen] = useState(readInitialSidebarOpen);
  const [draftsByChat, setDraftsByChat] = useState<Record<string, string>>({});
  const [storageWarningDismissed, setStorageWarningDismissed] = useState(false);
  const {
    messages,
    isLoading,
    activeSessionId,
    chatList,
    loadingChatIds,
    unseenChatIds,
    storageError,
    handleNewChat: controllerNewChat,
    handleSelectChat: controllerSelectChat,
    handleDeleteChat: controllerDeleteChat,
    handleClearHistory: controllerClearHistory,
    handleSend,
    handleStop,
    handleRetry,
  } = useChatController({
    errorMessage: t("errorMessage"),
    stoppedMessage: t("requestStopped"),
  });

  const closeSidebarOnMobile = useCallback(() => {
    const isMobile = typeof window !== "undefined" && window.matchMedia?.("(max-width: 768px)").matches;
    if (isMobile) setSidebarOpen(false);
  }, []);

  const toggleSidebar = useCallback(() => {
    setSidebarOpen((current) => {
      const next = !current;
      try {
        localStorage.setItem("modsa-sidebar-open", String(next));
      } catch {
        /* ignore */
      }
      return next;
    });
  }, []);

  const handleNewChat = useCallback(() => {
    controllerNewChat();
    closeSidebarOnMobile();
  }, [controllerNewChat, closeSidebarOnMobile]);

  const handleDraftChange = useCallback(
    (draft: string) => {
      setDraftsByChat((current) => ({ ...current, [activeSessionId]: draft }));
    },
    [activeSessionId]
  );

  const handleClearHistory = useCallback(() => {
    const cleared = controllerClearHistory();
    if (cleared) setDraftsByChat({});
    return cleared;
  }, [controllerClearHistory]);

  const handleSelectChat = useCallback(
    (id: string) => {
      controllerSelectChat(id);
      closeSidebarOnMobile();
    },
    [controllerSelectChat, closeSidebarOnMobile]
  );

  const handleDeleteChat = useCallback(
    (id: string) => {
      controllerDeleteChat(id);
      setDraftsByChat((current) => {
        if (!(id in current)) return current;
        const next = { ...current };
        delete next[id];
        return next;
      });
      closeSidebarOnMobile();
    },
    [controllerDeleteChat, closeSidebarOnMobile]
  );

  const handleStarterSelect = useCallback(
    (question: string) => {
      handleSend(question);
    },
    [handleSend]
  );

  useEffect(() => {
    if (storageError) setStorageWarningDismissed(false);
  }, [storageError]);

  return (
    <div className="app-layout" id="app-layout">
      <a href="#chat-input" className="skip-link">
        {t("skipToInput")}
      </a>
      <Sidebar
        isOpen={sidebarOpen}
        onToggle={toggleSidebar}
        chatList={chatList}
        loadingChatIds={loadingChatIds}
        unseenChatIds={unseenChatIds}
        activeSessionId={activeSessionId}
        onNewChat={handleNewChat}
        onSelectChat={handleSelectChat}
        onDeleteChat={handleDeleteChat}
        onClearHistory={handleClearHistory}
      />

      <main className="main-area" id="main-area">
        <header className="top-bar" id="top-bar">
          <button
            className="menu-btn"
            onClick={toggleSidebar}
            id="btn-menu"
            aria-label="Toggle menu"
            aria-expanded={sidebarOpen}
            aria-controls="sidebar"
          >
            <svg width="22" height="22" viewBox="0 0 22 22" fill="none">
              <path
                d="M4 6H18M4 11H18M4 16H18"
                stroke="currentColor"
                strokeWidth="1.8"
                strokeLinecap="round"
              />
            </svg>
          </button>
          <span className="top-bar-title">{t("appName")}</span>
          <button
            className="new-chat-topbar"
            onClick={handleNewChat}
            title={t("newChat")}
            aria-label={t("newChat")}
            id="btn-new-chat-top"
          >
            <svg width="18" height="18" viewBox="0 0 18 18" fill="none">
              <path
                d="M9 3V15M3 9H15"
                stroke="currentColor"
                strokeWidth="2"
                strokeLinecap="round"
              />
            </svg>
          </button>
        </header>

        {storageError && !storageWarningDismissed && (
          <div className="storage-warning" role="status">
            <span>{t("storageWarning")}</span>
            <button
              type="button"
              className="storage-warning-dismiss"
              onClick={() => setStorageWarningDismissed(true)}
              aria-label={t("close")}
              title={t("close")}
            >
              <svg width="14" height="14" viewBox="0 0 14 14" fill="none" aria-hidden="true">
                <path d="M3.5 3.5L10.5 10.5M10.5 3.5L3.5 10.5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
              </svg>
            </button>
          </div>
        )}

        <ChatPanel
          messages={messages}
          isLoading={isLoading}
          onStarterSelect={handleStarterSelect}
          onRetry={handleRetry}
        />

        <InputArea
          onSend={handleSend}
          isLoading={isLoading}
          onStop={handleStop}
          sessionId={activeSessionId}
          draft={draftsByChat[activeSessionId] || ""}
          onDraftChange={handleDraftChange}
        />
      </main>
    </div>
  );
}
