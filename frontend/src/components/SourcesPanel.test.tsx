import { describe, expect, it } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";
import { LanguageProvider } from "../i18n/LanguageContext";
import SourcesPanel, { safeSourceUrl } from "./SourcesPanel";

function renderSources(sources: unknown) {
  return render(
    <LanguageProvider>
      <SourcesPanel sources={sources} messageId="source-test" />
    </LanguageProvider>
  );
}

describe("SourcesPanel evidence presentation", () => {
  it("shows an explicit no-source state without confidence wording", () => {
    renderSources([]);

    const status = screen.getByRole("status");
    expect(status.textContent).toContain("No sources available");
    expect(status.textContent).not.toMatch(/confidence/i);
  });

  it("shows evidence coverage and safely filters source URLs", () => {
    const { container } = renderSources([
      { title: "Handbook", url: "https://example.com/handbook" },
      { title: "Unsafe", url: "javascript:alert(1)" },
    ]);

    expect(screen.getByText("Evidence coverage")).not.toBeNull();
    fireEvent.click(screen.getByRole("button", { name: /Evidence coverage/i }));
    expect(container.querySelector('a[href="https://example.com/handbook"]')).not.toBeNull();
    expect(container.querySelector('a[href^="javascript:"]')).toBeNull();
  });
});

describe("safeSourceUrl", () => {
  it("allows http, https, and anchors only", () => {
    expect(safeSourceUrl("https://example.com")).toBe("https://example.com/");
    expect(safeSourceUrl("http://example.com/a")).toBe("http://example.com/a");
    expect(safeSourceUrl("#sources")).toBe("#sources");
    expect(safeSourceUrl("javascript:alert(1)")).toBe("");
    expect(safeSourceUrl("data:text/html,evil")).toBe("");
  });
});
