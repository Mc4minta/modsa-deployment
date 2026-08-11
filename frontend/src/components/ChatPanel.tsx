import { useRef, useEffect, useState } from "react";
import { useLanguage } from "../i18n/LanguageContext";
import MessageBubble from "./MessageBubble";
import StarterQuestions from "./StarterQuestions";
import logoSvg from "../assets/logo.svg";
import type { Message } from "../types";

interface ChatPanelProps {
  messages: Message[];
  isLoading: boolean;
  onStarterSelect: (question: string) => void;
  onRetry: (question: string) => void;
  onViewSources: (message: Message) => void;
}

export default function ChatPanel({ messages, isLoading, onStarterSelect, onRetry, onViewSources }: ChatPanelProps) {
  const { t } = useLanguage();
  const chatPanelRef = useRef<HTMLDivElement>(null);
  const bottomRef = useRef<HTMLDivElement>(null);
  const isNearBottomRef = useRef(true);
  const [prefersReducedMotion, setPrefersReducedMotion] = useState(() => (
    typeof window !== "undefined" && typeof window.matchMedia === "function"
      ? window.matchMedia("(prefers-reduced-motion: reduce)").matches
      : false
  ));

  useEffect(() => {
    if (typeof window === "undefined" || typeof window.matchMedia !== "function") return undefined;
    const mediaQuery = window.matchMedia("(prefers-reduced-motion: reduce)");
    const handleChange = (event: MediaQueryListEvent) => setPrefersReducedMotion(event.matches);
    mediaQuery.addEventListener?.("change", handleChange);
    return () => mediaQuery.removeEventListener?.("change", handleChange);
  }, []);

  const handleScroll = () => {
    const element = chatPanelRef.current;
    if (!element) return;
    isNearBottomRef.current = element.scrollHeight - element.scrollTop - element.clientHeight < 48;
  };

  useEffect(() => {
    if (isNearBottomRef.current) {
      bottomRef.current?.scrollIntoView({
        behavior: prefersReducedMotion ? "auto" : "smooth",
        block: "end",
      });
    }
  }, [messages, isLoading, prefersReducedMotion]);

  const isEmpty = messages.length === 0;

  return (
    <div
      ref={chatPanelRef}
      className="chat-panel"
      id="chat-panel"
      onScroll={handleScroll}
      aria-label={t("appName")}
    >
      {isEmpty ? (
        <div className="welcome-state">
          <div className="welcome-logo">
            <img src={logoSvg} alt="MOD-SA" className="welcome-logo-img" />
            <div className="welcome-logo-glow" />
          </div>
          <h1 className="welcome-title">{t("welcomeTitle")}</h1>
          <p className="welcome-subtitle">{t("welcomeSubtitle")}</p>
          <p className="welcome-hint">{t("welcomeHint")}</p>
          <StarterQuestions onSelect={onStarterSelect} />
        </div>
      ) : (
        <div
          className="messages-container"
          role="log"
          aria-live="polite"
          aria-relevant="additions text"
          aria-busy={isLoading}
        >
          {messages
            .filter((msg) => msg.status !== "pending")
            .map((msg) => (
              <MessageBubble key={msg.id} message={msg} onRetry={onRetry} onViewSources={onViewSources} />
            ))}
          {isLoading && (
            <div className="message-row message-ai" role="status" aria-live="polite">
              <div className="avatar avatar-ai" aria-hidden="true">
                <svg width="20" height="20" viewBox="0 0 20 20" fill="none">
                  <path d="M10 2L12 7H18L13 10.5L15 16L10 12.5L5 16L7 10.5L2 7H8L10 2Z" fill="currentColor" />
                </svg>
              </div>
              <div className="message-content-wrapper">
                <div className="message-bubble bubble-ai">
                  <div className="typing-indicator" id="typing-indicator">
                    <span className="typing-dot" />
                    <span className="typing-dot" />
                    <span className="typing-dot" />
                    <span className="typing-label">{t("thinking")}</span>
                  </div>
                </div>
              </div>
            </div>
          )}
          <div ref={bottomRef} aria-hidden="true" />
        </div>
      )}
    </div>
  );
}
