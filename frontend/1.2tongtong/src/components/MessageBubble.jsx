import { useEffect, useState } from "react";
import ReactMarkdown from "react-markdown";
import rehypeSanitize from "rehype-sanitize";
import remarkGfm from "remark-gfm";
import logoSvg from "../assets/logo.svg";
import { useLanguage } from "../i18n/useLanguage";
import { Icon } from "./Icon";
import { SourcesPanel } from "./SourcesPanel";

const ERROR_MESSAGE_KEYS = {
  network: "errorNetwork",
  timeout: "errorTimeout",
  rate_limited: "errorRateLimited",
  request_rejected: "errorRejected",
  server_error: "errorServer",
  invalid_response: "errorInvalid",
};

function safeUrlTransform(value) {
  if (value.startsWith("#")) return value;
  try {
    const url = new URL(value, window.location.origin);
    return url.protocol === "http:" || url.protocol === "https:" ? value : "";
  } catch {
    return "";
  }
}

const markdownComponents = {
  table({ children }) {
    return (
      <div className="table-scroll">
        <table>{children}</table>
      </div>
    );
  },
  th({ children }) {
    return <th scope="col">{children}</th>;
  },
  a({ href = "", children }) {
    if (!href) return <span>{children}</span>;
    const internal = href.startsWith("#");
    return (
      <a
        href={href}
        target={internal ? undefined : "_blank"}
        rel={internal ? undefined : "noopener noreferrer"}
      >
        {children}
      </a>
    );
  },
};

export function MessageBubble({ message, onRetry }) {
  const { lang, t } = useLanguage();
  const [copied, setCopied] = useState(false);
  const isUser = message.role === "user";
  const isError = message.status === "error";
  const isStopped = message.status === "stopped";

  useEffect(() => {
    if (!copied) return undefined;
    const timer = window.setTimeout(() => setCopied(false), 2_000);
    return () => window.clearTimeout(timer);
  }, [copied]);

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(message.content);
      setCopied(true);
    } catch {
      setCopied(false);
    }
  };

  const time = message.timestamp
    ? new Intl.DateTimeFormat(lang === "th" ? "th-TH" : "en-US", {
        hour: "2-digit",
        minute: "2-digit",
      }).format(message.timestamp)
    : "";

  const displayedContent = isError
    ? t(ERROR_MESSAGE_KEYS[message.errorCode] || "errorGeneric")
    : message.content;

  return (
    <article className={`message-row ${isUser ? "message-user" : "message-ai"}`}>
      {!isUser && (
        <div className="avatar" aria-hidden="true">
          <img src={logoSvg} alt="" />
        </div>
      )}
      <div className="message-content-wrapper">
        <div className="message-heading">
          <strong>{isUser ? t("userLabel") : t("answerLabel")}</strong>
          {time && <time dateTime={new Date(message.timestamp).toISOString()}>{time}</time>}
        </div>

        <div
          className={`message-bubble ${isError ? "message-error" : ""} ${
            isStopped ? "message-stopped" : ""
          }`}
          role={isError ? "alert" : undefined}
        >
          {isUser || isError || isStopped ? (
            <p>{displayedContent}</p>
          ) : (
            <ReactMarkdown
              remarkPlugins={[remarkGfm]}
              rehypePlugins={[rehypeSanitize]}
              components={markdownComponents}
              urlTransform={safeUrlTransform}
            >
              {displayedContent}
            </ReactMarkdown>
          )}
        </div>

        {!isUser && (
          <div className="message-actions">
            {!isError && !isStopped && (
              <button
                className="message-action-button"
                onClick={handleCopy}
                type="button"
              >
                <Icon name="copy" size={15} />
                {copied ? t("copied") : t("copyMessage")}
              </button>
            )}
            {isError && message.originalQuestion && (
              <button
                className="retry-button"
                onClick={() => onRetry(message.originalQuestion)}
                type="button"
              >
                {t("retry")}
              </button>
            )}
          </div>
        )}

        {!isUser && !isError && !isStopped && (
          <SourcesPanel sources={message.sources} confidence={message.confidence} />
        )}
      </div>
    </article>
  );
}
