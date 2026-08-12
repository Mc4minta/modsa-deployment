import { useEffect, useRef, useState } from "react";
import { useLanguage } from "../i18n/LanguageContext";
import SourcesPanel, { normalizeSources } from "./SourcesPanel";
import type { Message } from "../types";

interface SourcesSidePanelProps {
  message: Message | null;
  onClose: () => void;
}

export default function SourcesSidePanel({ message, onClose }: SourcesSidePanelProps) {
  const { t } = useLanguage();
  const isOpen = Boolean(message);
  const panelRef = useRef<HTMLElement>(null);
  const closeButtonRef = useRef<HTMLButtonElement>(null);
  const previousFocusRef = useRef<HTMLElement | null>(null);
  const [displayMessage, setDisplayMessage] = useState<Message | null>(null);

  useEffect(() => {
    if (message) setDisplayMessage(message);
  }, [message]);

  const count = displayMessage ? normalizeSources(displayMessage.sources).length : 0;

  useEffect(() => {
    if (!isOpen) return undefined;
    previousFocusRef.current = document.activeElement as HTMLElement | null;
    const focusTimer = window.requestAnimationFrame(() => closeButtonRef.current?.focus());
    return () => {
      window.cancelAnimationFrame(focusTimer);
      const target = previousFocusRef.current;
      if (target?.isConnected && typeof target.focus === "function") target.focus();
    };
  }, [isOpen]);

  useEffect(() => {
    if (!isOpen) return undefined;

    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        event.preventDefault();
        onClose();
        return;
      }
      if (event.key !== "Tab" || !panelRef.current) return;

      const focusable = Array.from(
        panelRef.current.querySelectorAll<HTMLElement>(
          'button:not([disabled]), [href], input:not([disabled]), textarea:not([disabled]), select:not([disabled]), [tabindex]:not([tabindex="-1"])'
        )
      ).filter((element) => element.offsetParent !== null);
      if (focusable.length === 0) return;
      const first = focusable[0];
      const last = focusable[focusable.length - 1];
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first.focus();
      }
    };

    document.addEventListener("keydown", handleKeyDown);
    return () => document.removeEventListener("keydown", handleKeyDown);
  }, [isOpen, onClose]);

  return (
    <>
      <button
        type="button"
        className={`sources-side-overlay ${isOpen ? "visible" : ""}`}
        onClick={onClose}
        aria-label={t("close")}
        tabIndex={isOpen ? 0 : -1}
      />
      <aside
        ref={panelRef}
        className={`sources-side-panel ${isOpen ? "open" : ""}`}
        id="sources-side-panel"
        aria-label={t("sources")}
        aria-hidden={!isOpen}
      >
        <div className="sources-side-header">
          <span className="sources-side-title">
            {t("sources")}
            {isOpen && <span className="sources-side-count">{count}</span>}
          </span>
          <button
            ref={closeButtonRef}
            type="button"
            className="sources-side-close"
            onClick={onClose}
            aria-label={t("close")}
            title={t("close")}
          >
            <svg width="18" height="18" viewBox="0 0 18 18" fill="none" aria-hidden="true">
              <path d="M4.5 4.5L13.5 13.5M13.5 4.5L4.5 13.5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
            </svg>
          </button>
        </div>

        {displayMessage && (
          <div className="sources-side-body">
            <SourcesPanel sources={displayMessage.sources} messageId={displayMessage.id} />
          </div>
        )}
      </aside>
    </>
  );
}
