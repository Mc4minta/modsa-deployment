import { useId, useState } from "react";
import { useLanguage } from "../i18n/useLanguage";
import { Icon } from "./Icon";

function getCoverage(confidence, sourceCount) {
  if (sourceCount === 0) return "none";
  if (confidence === "high" && sourceCount >= 3) return "strong";
  if (sourceCount >= 2) return "moderate";
  return "limited";
}

function getSafeUrl(value) {
  if (!value) return null;
  try {
    const url = new URL(value, window.location.origin);
    return url.protocol === "http:" || url.protocol === "https:" ? url : null;
  } catch {
    return null;
  }
}

function getSourceType(url, t) {
  if (!url) return t("localSource");
  return url.hostname === "kmutt.ac.th" || url.hostname.endsWith(".kmutt.ac.th")
    ? t("officialSource")
    : t("externalSource");
}

export function SourcesPanel({ sources = [], confidence = "low" }) {
  const { t } = useLanguage();
  const [expanded, setExpanded] = useState(false);
  const panelId = useId();
  const coverage = getCoverage(confidence, sources.length);
  const coverageLabel = t(
    {
      strong: "evidenceStrong",
      moderate: "evidenceModerate",
      limited: "evidenceLimited",
      none: "evidenceNone",
    }[coverage],
  );

  if (sources.length === 0) {
    return (
      <aside className="evidence-notice evidence-none" role="note">
        <strong>{coverageLabel}</strong>
        <span>{t("noSources")}</span>
      </aside>
    );
  }

  return (
    <section className="sources-panel" aria-labelledby={`${panelId}-title`}>
      <button
        className="sources-toggle"
        onClick={() => setExpanded((current) => !current)}
        type="button"
        aria-expanded={expanded}
        aria-controls={`${panelId}-content`}
      >
        <span className="sources-summary">
          <span className="sources-icon" aria-hidden="true">
            {sources.length}
          </span>
          <span>
            <strong id={`${panelId}-title`}>{t("sources")}</strong>
            <small>{coverageLabel}</small>
          </span>
        </span>
        <span className={`source-chevron ${expanded ? "expanded" : ""}`}>
          <Icon name="chevronDown" size={17} />
        </span>
      </button>

      {expanded && (
        <div id={`${panelId}-content`} className="sources-content">
          <p className="evidence-disclaimer">{t("evidenceDisclaimer")}</p>
          <div className="sources-list">
            {sources.map((source, index) => {
              const safeUrl = getSafeUrl(source.url);
              const key = `${source.source || source.title}-${source.page || "na"}-${index}`;
              return (
                <article className="source-card" key={key}>
                  <span className="source-number" aria-hidden="true">
                    {index + 1}
                  </span>
                  <div className="source-card-content">
                    <strong>{source.title || source.source || `Source ${index + 1}`}</strong>
                    <div className="source-meta">
                      {source.department && <span>{source.department}</span>}
                      {source.page && (
                        <span>
                          {t("sourcePage")} {source.page}
                        </span>
                      )}
                      <span>{getSourceType(safeUrl, t)}</span>
                    </div>
                    {source.title && source.source && (
                      <span className="source-path">{source.source}</span>
                    )}
                  </div>
                  {safeUrl && (
                    <a
                      className="source-link"
                      href={safeUrl.href}
                      target="_blank"
                      rel="noopener noreferrer"
                    >
                      {t("viewSource")}
                      <Icon name="arrowRight" size={15} />
                    </a>
                  )}
                </article>
              );
            })}
          </div>
        </div>
      )}
    </section>
  );
}
