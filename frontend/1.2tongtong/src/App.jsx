import { useCallback, useEffect, useRef, useState } from "react";
import { ChatPanel } from "./components/ChatPanel";
import { InputArea } from "./components/InputArea";
import { Sidebar } from "./components/Sidebar";
import { TopBar } from "./components/TopBar";
import { useBackendHealth } from "./hooks/useBackendHealth";
import { useLanguage } from "./i18n/useLanguage";
import { ApiError, askQuestion, cancelRequest } from "./services/api";
import { validateQuestion } from "./utils/guards";
import {
  clearAllChats,
  deleteChat,
  generateId,
  getChatList,
  loadChat,
  saveChat,
} from "./utils/storage";
import "./App.css";

export function App() {
  const { lang, t } = useLanguage();
  const { status: healthStatus, refresh: refreshHealth } = useBackendHealth();
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [messages, setMessages] = useState([]);
  const [isLoading, setIsLoading] = useState(false);
  const [sessionId, setSessionId] = useState(() => generateId());
  const [chatList, setChatList] = useState(() => getChatList());
  const sessionRef = useRef(sessionId);
  const requestRef = useRef(null);

  useEffect(() => {
    if (messages.length === 0) return;
    saveChat(sessionId, messages);
    setChatList(getChatList());
  }, [messages, sessionId]);

  useEffect(
    () => () => {
      cancelRequest();
      requestRef.current = null;
    },
    [],
  );

  const abortActiveRequest = useCallback(() => {
    cancelRequest();
    requestRef.current = null;
    setIsLoading(false);
  }, []);

  const changeSession = useCallback(
    (nextSessionId, nextMessages) => {
      abortActiveRequest();
      sessionRef.current = nextSessionId;
      setSessionId(nextSessionId);
      setMessages(nextMessages);
      setSidebarOpen(false);
    },
    [abortActiveRequest],
  );

  const handleNewChat = useCallback(() => {
    changeSession(generateId(), []);
  }, [changeSession]);

  const handleSelectChat = useCallback(
    (id) => {
      changeSession(id, loadChat(id));
    },
    [changeSession],
  );

  const handleDeleteChat = useCallback(
    (id) => {
      deleteChat(id);
      setChatList(getChatList());
      if (id === sessionRef.current) {
        changeSession(generateId(), []);
      }
    },
    [changeSession],
  );

  const handleClearHistory = useCallback(() => {
    clearAllChats();
    setChatList([]);
    changeSession(generateId(), []);
  }, [changeSession]);

  const handleSend = useCallback(
    async (rawQuestion) => {
      const validation = validateQuestion(rawQuestion);
      if (!validation.ok || requestRef.current) return;

      const question = validation.question;
      const originSessionId = sessionRef.current;
      const requestId = generateId();
      const userMessage = {
        id: generateId(),
        role: "user",
        content: question,
        timestamp: Date.now(),
        status: "complete",
      };

      setMessages((current) => [...current, userMessage]);
      setIsLoading(true);
      requestRef.current = { id: requestId, sessionId: originSessionId };

      try {
        const data = await askQuestion(question, lang);
        if (
          requestRef.current?.id !== requestId ||
          sessionRef.current !== originSessionId
        ) {
          return;
        }

        setMessages((current) => [
          ...current,
          {
            id: generateId(),
            role: "assistant",
            content: data.answer,
            sources: data.sources,
            confidence: data.confidence,
            timestamp: Date.now(),
            status: "complete",
          },
        ]);
      } catch (error) {
        if (
          requestRef.current?.id !== requestId ||
          sessionRef.current !== originSessionId
        ) {
          return;
        }
        if (error instanceof ApiError && error.code === "cancelled") return;

        setMessages((current) => [
          ...current,
          {
            id: generateId(),
            role: "assistant",
            content: "",
            sources: [],
            confidence: "low",
            timestamp: Date.now(),
            status: "error",
            errorCode: error instanceof ApiError ? error.code : "unknown",
            originalQuestion: question,
          },
        ]);
      } finally {
        if (requestRef.current?.id === requestId) {
          requestRef.current = null;
          setIsLoading(false);
        }
      }
    },
    [lang],
  );

  const handleStop = useCallback(() => {
    if (!requestRef.current) return;
    const requestSessionId = requestRef.current.sessionId;
    abortActiveRequest();

    if (requestSessionId === sessionRef.current) {
      setMessages((current) => [
        ...current,
        {
          id: generateId(),
          role: "assistant",
          content: t("requestStopped"),
          timestamp: Date.now(),
          status: "stopped",
        },
      ]);
    }
  }, [abortActiveRequest, t]);

  const toggleSidebar = useCallback(() => {
    setSidebarOpen((current) => !current);
  }, []);

  return (
    <div className="app-layout">
      <Sidebar
        isOpen={sidebarOpen}
        onToggle={toggleSidebar}
        chatList={chatList}
        activeSessionId={sessionId}
        onNewChat={handleNewChat}
        onSelectChat={handleSelectChat}
        onDeleteChat={handleDeleteChat}
        onClearHistory={handleClearHistory}
      />

      <main className="main-area">
        <TopBar
          healthStatus={healthStatus}
          onRefreshHealth={refreshHealth}
          onOpenMenu={toggleSidebar}
          onNewChat={handleNewChat}
        />
        <ChatPanel
          messages={messages}
          isLoading={isLoading}
          onStarterSelect={handleSend}
          onRetry={handleSend}
        />
        <InputArea onSend={handleSend} isLoading={isLoading} onStop={handleStop} />
      </main>
    </div>
  );
}
