import { useId, useState } from "react";
import { useLanguage } from "../i18n/LanguageContext";
import type { Source } from "../types";

export function safeSourceUrl(value: unknown): string {
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

function normalizeSources(sources: unknown): Source[] {
  if (!Array.isArray(sources)) return [];

  return sources.filter((source): source is Source => Boolean(source) && typeof source === "object");
}

function sourceKey(source: Source, index: number): string {
  const stablePart = source.id || source.url || source.source || source.title;
  return `${stablePart || "source"}-${index}`;
}

interface GroupedSource extends Source {
  pages: (string | number)[];
}

function hasPage(source: Source): boolean {
  return source.page !== undefined && source.page !== null && source.page !== "";
}

function groupSourcesByDocument(sources: Source[]): GroupedSource[] {
  const order: string[] = [];
  const groups = new Map<string, GroupedSource>();

  sources.forEach((source) => {
    const identity = source.source || source.url || source.title || "";
    const key = identity || `__ungrouped-${groups.size}`;
    const existing = groups.get(key);
    if (existing) {
      if (hasPage(source) && !existing.pages.includes(source.page)) existing.pages.push(source.page);
      return;
    }
    order.push(key);
    groups.set(key, { ...source, pages: hasPage(source) ? [source.page] : [] });
  });

  return order.map((key) => groups.get(key)!);
}

function isPdfUrl(url: string): boolean {
  return /\.pdf(?:$|[?#])/i.test(url);
}

function getEvidenceLabel(t: (key: string) => string): string {
  const translated = t("evidenceCoverage");
  return translated === "evidenceCoverage" ? "Evidence coverage" : translated;
}

function getEvidenceDisclaimer(t: (key: string) => string): string {
  const translated = t("evidenceDisclaimer");
  return translated === "evidenceDisclaimer"
    ? "Sources show retrieved evidence; they do not guarantee answer correctness."
    : translated;
}

interface SourcesPanelProps {
  sources: unknown;
  messageId?: string;
}

export default function SourcesPanel({ sources, messageId }: SourcesPanelProps) {
  const { t } = useLanguage();
  const [expanded, setExpanded] = useState(false);
  const panelId = useId().replace(/:/g, "");
  const normalizedSources = normalizeSources(sources);
  const hasSources = normalizedSources.length > 0;
  const evidenceLabel = getEvidenceLabel(t);
  const disclaimer = getEvidenceDisclaimer(t);
  const scopedId = messageId || panelId;

  if (!hasSources) {
    return (
      <div className="sources-panel evidence-none" id={`sources-panel-${scopedId}`} role="status">
        <div className="evidence-empty-label">
          <svg className="evidence-icon" width="13" height="13" viewBox="0 0 14 14" fill="none" aria-hidden="true">
            <path d="M3 1.5H8.5L11 4V12.5H3V1.5Z" stroke="currentColor" strokeWidth="1.2" strokeLinejoin="round" />
            <path d="M4.5 3.5L2.5 1.5M2.5 3.5L4.5 1.5" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round" />
          </svg>
          <span>{t("noSources")}</span>
        </div>
        <p className="evidence-disclaimer">{disclaimer}</p>
      </div>
    );
  }

  const groupedSources = groupSourcesByDocument(normalizedSources);
  const countLabel = `${normalizedSources.length} ${normalizedSources.length === 1 ? t("sourceUnit") : t("sourcesUnit")}`;

  return (
    <section
      className="sources-panel evidence-coverage"
      id={`sources-panel-${scopedId}`}
      aria-label={evidenceLabel}
    >
      <button
        className="sources-toggle"
        onClick={() => setExpanded((current) => !current)}
        id={`sources-toggle-${scopedId}`}
        aria-expanded={expanded}
        aria-controls={`sources-list-${scopedId}`}
        type="button"
      >
        <span className="sources-toggle-left">
          <span className="evidence-badge">
            <svg className="evidence-icon" width="12" height="12" viewBox="0 0 14 14" fill="none" aria-hidden="true">
              <path d="M2.5 7.5L5.5 10.5L11.5 3.5" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" />
            </svg>
            {evidenceLabel}
          </span>
          <span className="sources-count">{countLabel}</span>
        </span>
        <svg
          className={`chevron-icon ${expanded ? "expanded" : ""}`}
          width="16"
          height="16"
          viewBox="0 0 16 16"
          fill="none"
          aria-hidden="true"
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

      <p className="evidence-disclaimer">{disclaimer}</p>

      {expanded && (
        <div className="sources-list" id={`sources-list-${scopedId}`}>
          {groupedSources.map((src, i) => {
            const title = src.title || src.source || `Source ${i + 1}`;
            const sourceUrl = safeSourceUrl(src.url);
            const isAnchor = sourceUrl.startsWith("#");
            const isExternal = sourceUrl && !isAnchor;
            const viewLabel = isPdfUrl(sourceUrl) ? t("viewDocument") : t("viewSource");
            const pageLabel = src.pages.length > 0 ? src.pages.join(", ") : "";

            return (
              <article className="source-card" key={sourceKey(src, i)}>
                <div className="source-card-header">
                  <svg
                    className="source-icon"
                    width="14"
                    height="14"
                    viewBox="0 0 14 14"
                    fill="none"
                    aria-hidden="true"
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
                  <span className="source-title">{title}</span>
                </div>

                <div className="source-meta">
                  {src.department && (
                    <span className="source-dept">
                      {t("department")}: {src.department}
                    </span>
                  )}
                  {pageLabel && (
                    <span className="source-page">
                      {t("page")} {pageLabel}
                    </span>
                  )}
                </div>

                {src.source && <div className="source-file">{src.source}</div>}

                {sourceUrl && (
                  <div className="source-actions">
                    <a
                      href={sourceUrl}
                      target={isAnchor ? undefined : "_blank"}
                      rel={isAnchor ? undefined : "noopener noreferrer"}
                      className="source-btn"
                    >
                      <svg width="12" height="12" viewBox="0 0 12 12" fill="none" aria-hidden="true">
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
                      {viewLabel}
                      {isExternal && <span className="sr-only"> ({t("opensNewTab")})</span>}
                    </a>
                  </div>
                )}
              </article>
            );
          })}
        </div>
      )}
    </section>
  );
}
