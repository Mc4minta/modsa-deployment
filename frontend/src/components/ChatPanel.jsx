import { useRef, useEffect } from "react";
import { useLanguage } from "../i18n/LanguageContext";
import MessageBubble from "./MessageBubble";
import StarterQuestions from "./StarterQuestions";
import logoSvg from "../assets/logo.svg";

export default function ChatPanel({ messages, isLoading, onStarterSelect }) {
  const { t } = useLanguage();
  const bottomRef = useRef(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, isLoading]);

  const isEmpty = messages.length === 0;

  return (
    <div className="chat-panel" id="chat-panel">
      {isEmpty ? (
        <div className="welcome-state">
          <div className="welcome-logo">
            <img src={logoSvg} alt="MOD-SA" className="welcome-logo-img" />
            <div className="welcome-logo-glow"></div>
          </div>
          <h1 className="welcome-title">{t("welcomeTitle")}</h1>
          <p className="welcome-subtitle">{t("welcomeSubtitle")}</p>
          <p className="welcome-hint">{t("welcomeHint")}</p>
          <StarterQuestions onSelect={onStarterSelect} />
        </div>
      ) : (
        <div className="messages-container">
          {messages.map((msg) => (
            <MessageBubble key={msg.id} message={msg} />
          ))}
          {isLoading && (
            <div className="message-row message-ai">
              <div className="avatar avatar-ai" aria-hidden="true">
                <svg width="20" height="20" viewBox="0 0 20 20" fill="none">
                  <path d="M10 2L12 7H18L13 10.5L15 16L10 12.5L5 16L7 10.5L2 7H8L10 2Z" fill="currentColor" />
                </svg>
              </div>
              <div className="message-content-wrapper">
                <div className="message-bubble bubble-ai">
                  <div className="typing-indicator" id="typing-indicator">
                    <span className="typing-dot"></span>
                    <span className="typing-dot"></span>
                    <span className="typing-dot"></span>
                    <span className="typing-label">{t("thinking")}</span>
                  </div>
                </div>
              </div>
            </div>
          )}
          <div ref={bottomRef} />
        </div>
      )}
    </div>
  );
}
