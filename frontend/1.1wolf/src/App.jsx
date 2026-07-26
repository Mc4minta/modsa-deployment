import { useState, useCallback, useEffect } from "react";
import { useLanguage } from "./i18n/LanguageContext";
import Sidebar from "./components/Sidebar";
import ChatPanel from "./components/ChatPanel";
import InputArea from "./components/InputArea";
import { askQuestion, cancelRequest } from "./services/api";
import {
  generateId,
  saveChat,
  loadChat,
  deleteChat,
  getChatList,
} from "./utils/storage";
import "./App.css";

export default function App() {
  const { t } = useLanguage();
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [messages, setMessages] = useState([]);
  const [isLoading, setIsLoading] = useState(false);
  const [sessionId, setSessionId] = useState(() => generateId());
  const [chatList, setChatList] = useState(() => getChatList());

  // Persist messages
  useEffect(() => {
    if (messages.length > 0) {
      saveChat(sessionId, messages);
      setChatList(getChatList());
    }
  }, [messages, sessionId]);

  const handleNewChat = useCallback(() => {
    setMessages([]);
    setSessionId(generateId());
    setSidebarOpen(false);
  }, []);

  const handleSelectChat = useCallback((id) => {
    const loaded = loadChat(id);
    setMessages(loaded);
    setSessionId(id);
    setSidebarOpen(false);
  }, []);

  const handleDeleteChat = useCallback(
    (id) => {
      deleteChat(id);
      setChatList(getChatList());
      if (id === sessionId) {
        setMessages([]);
        setSessionId(generateId());
      }
    },
    [sessionId]
  );

  const handleSend = useCallback(
    async (text) => {
      if (!text.trim()) return;

      const userMsg = {
        id: generateId(),
        role: "user",
        content: text,
        timestamp: Date.now(),
      };

      setMessages((prev) => [...prev, userMsg]);
      setIsLoading(true);

      try {
        const data = await askQuestion(text);
        const aiMsg = {
          id: generateId(),
          role: "assistant",
          content: data.answer,
          sources: data.sources,
          confidence: data.confidence,
          timestamp: Date.now(),
        };
        setMessages((prev) => [...prev, aiMsg]);
      } catch (err) {
        if (err.name !== "AbortError") {
          const errMsg = {
            id: generateId(),
            role: "assistant",
            content: t("errorMessage"),
            sources: [],
            confidence: "low",
            timestamp: Date.now(),
          };
          setMessages((prev) => [...prev, errMsg]);
        }
      } finally {
        setIsLoading(false);
      }
    },
    [t]
  );

  const handleStop = useCallback(() => {
    cancelRequest();
    setIsLoading(false);
  }, []);

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
        onToggle={() => setSidebarOpen(!sidebarOpen)}
        chatList={chatList}
        activeSessionId={sessionId}
        onNewChat={handleNewChat}
        onSelectChat={handleSelectChat}
        onDeleteChat={handleDeleteChat}
      />

      <main className="main-area" id="main-area">
        <header className="top-bar" id="top-bar">
          <button
            className="menu-btn"
            onClick={() => setSidebarOpen(!sidebarOpen)}
            id="btn-menu"
            aria-label="Toggle menu"
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

        <ChatPanel
          messages={messages}
          isLoading={isLoading}
          onStarterSelect={handleStarterSelect}
        />

        <InputArea
          onSend={handleSend}
          isLoading={isLoading}
          onStop={handleStop}
        />
      </main>
    </div>
  );
}
