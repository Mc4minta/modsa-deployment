import { useState, useCallback } from "react";
import { useLanguage } from "./i18n/LanguageContext";
import Sidebar from "./components/Sidebar";
import ChatPanel from "./components/ChatPanel";
import InputArea from "./components/InputArea";
import { useChatController } from "./hooks/useChatController";
import "./App.css";

export default function App() {
  const { t } = useLanguage();
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [draftsByChat, setDraftsByChat] = useState({});
  const {
    messages,
    isLoading,
    activeSessionId,
    chatList,
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

  const toggleSidebar = useCallback(() => setSidebarOpen((current) => !current), []);

  const handleNewChat = useCallback(() => {
    controllerNewChat();
    setSidebarOpen(false);
  }, [controllerNewChat]);

  const handleDraftChange = useCallback(
    (draft) => {
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
    (id) => {
      controllerSelectChat(id);
      setSidebarOpen(false);
    },
    [controllerSelectChat]
  );

  const handleDeleteChat = useCallback(
    (id) => {
      controllerDeleteChat(id);
      setDraftsByChat((current) => {
        if (!(id in current)) return current;
        const next = { ...current };
        delete next[id];
        return next;
      });
      setSidebarOpen(false);
    },
    [controllerDeleteChat]
  );

  const handleStarterSelect = useCallback(
    (question) => {
      handleSend(question);
    },
    [handleSend]
  );

  return (
    <div className="app-layout" id="app-layout">
      <Sidebar
        isOpen={sidebarOpen}
        onToggle={toggleSidebar}
        chatList={chatList}
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

        {storageError && (
          <div className="storage-warning" role="status">
            {t("storageWarning")}
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
