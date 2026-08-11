import { useEffect, useRef, useState, type ComponentPropsWithoutRef } from "react";
import ReactMarkdown, { type Components } from "react-markdown";
import rehypeSanitize from "rehype-sanitize";
import remarkGfm from "remark-gfm";
import { useLanguage } from "../i18n/LanguageContext";
import { normalizeSources } from "./SourcesPanel";
import type { Message } from "../types";

/**
 * Only allow links which can be safely opened by the chat renderer.
 * ReactMarkdown still receives the URL, but an empty result is rendered as
 * text by the link component below instead of as a clickable element.
 */
export function safeMarkdownUrl(value: unknown): string {
  if (typeof value !== "string") return "";

  const url = value.trim();
  if (url.startsWith("#")) return url;

  try {
    const parsed = new URL(url);
    return parsed.protocol === "http:" || parsed.protocol === "https:"
      ? parsed.toString()
      : "";
  } catch {
    return "";
  }
}

type CodeProps = ComponentPropsWithoutRef<"code"> & { node?: unknown; inline?: boolean };

const markdownComponents: Components = {
  p: ({ node: _node, ...props }) => <p className="md-p" {...props} />,
  h1: ({ node: _node, ...props }) => <h2 className="md-h2" {...props} />,
  h2: ({ node: _node, ...props }) => <h3 className="md-h3" {...props} />,
  h3: ({ node: _node, ...props }) => <h4 className="md-h4" {...props} />,
  h4: ({ node: _node, ...props }) => <h4 className="md-h4" {...props} />,
  ul: ({ node: _node, ...props }) => <ul className="md-ul" {...props} />,
  ol: ({ node: _node, ...props }) => <ol className="md-ol" {...props} />,
  li: ({ node: _node, ...props }) => <li className="md-li" {...props} />,
  pre: ({ node: _node, ...props }) => <pre className="md-code-block" {...props} />,
  code: ({ node: _node, inline, className, children, ...props }: CodeProps) => {
    const languageClass = className || "";
    return (
      <code
        className={inline ? "md-inline-code" : `md-code-block-code ${languageClass}`.trim()}
        {...props}
      >
        {children}
      </code>
    );
  },
  blockquote: ({ node: _node, ...props }) => <blockquote className="md-blockquote" {...props} />,
  table: ({ node: _node, ...props }) => (
    <div className="md-table-wrapper">
      <table className="md-table" {...props} />
    </div>
  ),
  a: ({ node: _node, href, children, ...props }) => {
    const safeHref = safeMarkdownUrl(href);
    if (!safeHref) {
      return <span className="md-link md-link-invalid">{children}</span>;
    }

    const isAnchor = safeHref.startsWith("#");
    return (
      <a
        {...props}
        href={safeHref}
        className="md-link"
        target={isAnchor ? undefined : "_blank"}
        rel={isAnchor ? undefined : "noopener noreferrer"}
      >
        {children}
      </a>
    );
  },
};

interface MessageBubbleProps {
  message: Message;
  onRetry?: (question: string) => void;
  onViewSources?: (message: Message) => void;
}

export default function MessageBubble({ message, onRetry, onViewSources }: MessageBubbleProps) {
  const { t } = useLanguage();
  const [copied, setCopied] = useState(false);
  const [menuOpen, setMenuOpen] = useState(false);
  const menuRef = useRef<HTMLDivElement>(null);
  const content = message.content;
  const isUser = message.role === "user";
  const isRecoverable = message.status === "error" || message.status === "stopped";
  const sourceCount = normalizeSources(message.sources).length;

  useEffect(() => {
    if (!copied) return undefined;
    const timeoutId = window.setTimeout(() => setCopied(false), 2000);
    return () => window.clearTimeout(timeoutId);
  }, [copied]);

  useEffect(() => {
    if (!menuOpen) return undefined;
    const handleClickOutside = (event: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(event.target as Node)) setMenuOpen(false);
    };
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") setMenuOpen(false);
    };
    document.addEventListener("mousedown", handleClickOutside);
    document.addEventListener("keydown", handleKeyDown);
    return () => {
      document.removeEventListener("mousedown", handleClickOutside);
      document.removeEventListener("keydown", handleKeyDown);
    };
  }, [menuOpen]);

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(content);
      setCopied(true);
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
            <p className="message-text">{content}</p>
          ) : isRecoverable ? (
            <p className="message-text message-error" role="alert">
              {content}
            </p>
          ) : (
            <div className="message-text message-markdown">
              <ReactMarkdown
                remarkPlugins={[remarkGfm]}
                rehypePlugins={[rehypeSanitize]}
                urlTransform={safeMarkdownUrl}
                components={markdownComponents}
              >
                {content}
              </ReactMarkdown>
            </div>
          )}
        </div>

        <div className="message-meta">
          {timeStr && <span className="message-time">{timeStr}</span>}
          {!isUser && !isRecoverable && (
            <button
              type="button"
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
          {!isUser && isRecoverable && message.originalQuestion && onRetry && (
            <button
              type="button"
              className="retry-button"
              onClick={() => onRetry(message.originalQuestion!)}
            >
              {t("retryMessage")}
            </button>
          )}
          {!isUser && !isRecoverable && message.status !== "pending" && onViewSources && (
            <div className="message-actions-wrap" ref={menuRef}>
              <button
                type="button"
                className="message-actions-btn"
                onClick={() => setMenuOpen((current) => !current)}
                aria-haspopup="menu"
                aria-expanded={menuOpen}
                aria-label={t("moreActions")}
                title={t("moreActions")}
              >
                <svg width="16" height="16" viewBox="0 0 16 16" fill="none" aria-hidden="true">
                  <circle cx="8" cy="3.2" r="1.2" fill="currentColor" />
                  <circle cx="8" cy="8" r="1.2" fill="currentColor" />
                  <circle cx="8" cy="12.8" r="1.2" fill="currentColor" />
                </svg>
              </button>
              {menuOpen && (
                <div className="message-actions-menu" role="menu">
                  <button
                    type="button"
                    role="menuitem"
                    className="message-actions-menu-item"
                    onClick={() => {
                      setMenuOpen(false);
                      onViewSources(message);
                    }}
                  >
                    {t("viewSources")} ({sourceCount})
                  </button>
                </div>
              )}
            </div>
          )}
        </div>
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
