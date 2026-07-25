import { useState } from "react";
import { useLanguage } from "../i18n/LanguageContext";

export default function SourcesPanel({ sources, confidence }) {
  const { t } = useLanguage();
  const [expanded, setExpanded] = useState(false);

  if (!sources || sources.length === 0) return null;

  const confClass =
    confidence === "high"
      ? "confidence-high"
      : confidence === "medium"
      ? "confidence-medium"
      : "confidence-low";

  const confLabel =
    confidence === "high"
      ? t("confidenceHigh")
      : confidence === "medium"
      ? t("confidenceMedium")
      : t("confidenceLow");

  const confIcon =
    confidence === "high" ? "✓" : confidence === "medium" ? "~" : "!";

  return (
    <div className={`sources-panel ${confClass}`} id="sources-panel">
      <button
        className="sources-toggle"
        onClick={() => setExpanded(!expanded)}
        id="sources-toggle"
        aria-expanded={expanded}
      >
        <div className="sources-toggle-left">
          <span className={`confidence-badge ${confClass}`}>
            <span className="confidence-icon">{confIcon}</span>
            {confLabel}
          </span>
          <span className="sources-count">
            {sources.length} {t("sources").toLowerCase()}
          </span>
        </div>
        <svg
          className={`chevron-icon ${expanded ? "expanded" : ""}`}
          width="16"
          height="16"
          viewBox="0 0 16 16"
          fill="none"
        >
          <path
            d="M4 6L8 10L12 6"
            stroke="currentColor"
            strokeWidth="1.5"
            strokeLinecap="round"
            strokeLinejoin="round"
          />
        </svg>
      </button>

      {expanded && (
        <div className="sources-list">
          {sources.map((src, i) => (
            <div className="source-card" key={i} id={`source-card-${i}`}>
              <div className="source-card-header">
                <svg
                  className="source-icon"
                  width="14"
                  height="14"
                  viewBox="0 0 14 14"
                  fill="none"
                >
                  <path
                    d="M3 1.5H8.5L11 4V12.5H3V1.5Z"
                    stroke="currentColor"
                    strokeWidth="1.2"
                    strokeLinejoin="round"
                  />
                  <path
                    d="M8.5 1.5V4H11"
                    stroke="currentColor"
                    strokeWidth="1.2"
                    strokeLinejoin="round"
                  />
                </svg>
                <span className="source-title">
                  {src.title || src.source || `Source ${i + 1}`}
                </span>
              </div>

              <div className="source-meta">
                {src.department && (
                  <span className="source-dept">
                    {t("department")}: {src.department}
                  </span>
                )}
                {src.page && (
                  <span className="source-page">
                    {t("page")} {src.page}
                  </span>
                )}
              </div>

              {src.source && (
                <div className="source-file">{src.source}</div>
              )}

              <div className="source-actions">
                {src.url && (
                  <a
                    href={src.url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="source-btn"
                    id={`source-view-${i}`}
                  >
                    <svg width="12" height="12" viewBox="0 0 12 12" fill="none">
                      <path
                        d="M5 1H2V10H10V7"
                        stroke="currentColor"
                        strokeWidth="1.2"
                        strokeLinecap="round"
                        strokeLinejoin="round"
                      />
                      <path
                        d="M7 1H11V5M11 1L5.5 6.5"
                        stroke="currentColor"
                        strokeWidth="1.2"
                        strokeLinecap="round"
                        strokeLinejoin="round"
                      />
                    </svg>
                    {t("viewSource")}
                  </a>
                )}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
