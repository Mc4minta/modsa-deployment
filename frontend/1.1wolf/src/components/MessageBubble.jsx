import { useState } from "react";
import { renderMarkdown } from "../utils/markdown";
import { useLanguage } from "../i18n/LanguageContext";
import SourcesPanel from "./SourcesPanel";

export default function MessageBubble({ message }) {
  const { t } = useLanguage();
  const [copied, setCopied] = useState(false);
  const isUser = message.role === "user";

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(message.content);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      /* clipboard not available */
    }
  };

  const timeStr = message.timestamp
    ? new Date(message.timestamp).toLocaleTimeString([], {
        hour: "2-digit",
        minute: "2-digit",
      })
    : "";

  return (
    <div
      className={`message-row ${isUser ? "message-user" : "message-ai"}`}
      id={`message-${message.id || "unknown"}`}
    >
      {!isUser && (
        <div className="avatar avatar-ai" aria-hidden="true">
          <svg width="20" height="20" viewBox="0 0 20 20" fill="none">
            <path
              d="M10 2L12 7H18L13 10.5L15 16L10 12.5L5 16L7 10.5L2 7H8L10 2Z"
              fill="currentColor"
            />
          </svg>
        </div>
      )}

      <div className="message-content-wrapper">
        <div className={`message-bubble ${isUser ? "bubble-user" : "bubble-ai"}`}>
          {isUser ? (
            <p className="message-text">{message.content}</p>
          ) : (
            <div
              className="message-text message-markdown"
              dangerouslySetInnerHTML={{
                __html: renderMarkdown(message.content),
              }}
            />
          )}
        </div>

        <div className="message-meta">
          {timeStr && <span className="message-time">{timeStr}</span>}
          {!isUser && (
            <button
              className="copy-btn"
              onClick={handleCopy}
              title={t("copyMessage")}
              id={`copy-btn-${message.id || "unknown"}`}
            >
              {copied ? (
                <>
                  <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
                    <path
                      d="M3 7L6 10L11 4"
                      stroke="currentColor"
                      strokeWidth="1.5"
                      strokeLinecap="round"
                      strokeLinejoin="round"
                    />
                  </svg>
                  {t("copied")}
                </>
              ) : (
                <>
                  <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
                    <rect
                      x="4.5"
                      y="4.5"
                      width="7"
                      height="7"
                      rx="1.5"
                      stroke="currentColor"
                      strokeWidth="1.2"
                    />
                    <path
                      d="M9.5 4.5V3C9.5 2.17157 8.82843 1.5 8 1.5H3C2.17157 1.5 1.5 2.17157 1.5 3V8C1.5 8.82843 2.17157 9.5 3 9.5H4.5"
                      stroke="currentColor"
                      strokeWidth="1.2"
                    />
                  </svg>
                  {t("copyMessage")}
                </>
              )}
            </button>
          )}
        </div>

        {!isUser && message.sources && (
          <SourcesPanel
            sources={message.sources}
            confidence={message.confidence}
          />
        )}
      </div>

      {isUser && (
        <div className="avatar avatar-user" aria-hidden="true">
          <svg width="18" height="18" viewBox="0 0 18 18" fill="none">
            <circle cx="9" cy="6" r="3" stroke="currentColor" strokeWidth="1.5" />
            <path
              d="M3 16C3 12.6863 5.68629 10 9 10C12.3137 10 15 12.6863 15 16"
              stroke="currentColor"
              strokeWidth="1.5"
              strokeLinecap="round"
            />
          </svg>
        </div>
      )}
    </div>
  );
}
