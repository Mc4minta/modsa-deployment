import { useEffect, useRef } from "react";
import { useLanguage } from "../i18n/useLanguage";
import logoSvg from "../assets/logo.svg";
import { Icon } from "./Icon";
import { MessageBubble } from "./MessageBubble";
import { StarterQuestions } from "./StarterQuestions";

export function ChatPanel({ messages, isLoading, onStarterSelect, onRetry }) {
  const { t } = useLanguage();
  const bottomRef = useRef(null);
  const isEmpty = messages.length === 0;

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [messages, isLoading]);

  return (
    <section
      className="chat-panel"
      aria-label={t("answerLabel")}
      role={isEmpty ? undefined : "log"}
      aria-live="polite"
      aria-busy={isLoading}
    >
      {isEmpty ? (
        <div className="welcome-state">
          <div className="welcome-heading">
            <span className="welcome-logo-shell">
              <img src={logoSvg} alt="" className="welcome-logo" />
            </span>
            <p className="eyebrow">KMUTT STUDENT AFFAIRS</p>
            <h1>{t("welcomeTitle")}</h1>
          </div>
          <p className="welcome-subtitle">{t("welcomeSubtitle")}</p>
          <p className="welcome-hint">{t("welcomeHint")}</p>
          <StarterQuestions onSelect={onStarterSelect} />
          <aside className="scope-notice">
            <Icon name="shield" size={18} />
            <span>
              <strong>{t("scopeTitle")}</strong>
              {t("scopeBody")}
            </span>
          </aside>
        </div>
      ) : (
        <div className="messages-container">
          {messages.map((message) => (
            <MessageBubble key={message.id} message={message} onRetry={onRetry} />
          ))}
          {isLoading && (
            <div className="thinking-state" role="status">
              <span className="thinking-mark" aria-hidden="true">
                <Icon name="sparkles" size={18} />
              </span>
              <span>{t("thinking")}</span>
            </div>
          )}
          <div ref={bottomRef} />
        </div>
      )}
    </section>
  );
}
