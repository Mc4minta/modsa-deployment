import { describe, expect, it } from "vitest";
import { render } from "@testing-library/react";
import { LanguageProvider } from "../i18n/LanguageContext";
import MessageBubble from "./MessageBubble";
import type { Source } from "../types";

function renderAssistant(content: string, sources: Source[] = []) {
  return render(
    <LanguageProvider>
      <MessageBubble
        message={{
          id: "render-test",
          role: "assistant",
          content,
          sources,
          status: "success",
          timestamp: Date.now(),
        }}
      />
    </LanguageProvider>
  );
}

describe("MessageBubble Markdown rendering", () => {
  it("renders GFM tables as semantic tables", () => {
    const { container } = renderAssistant(
      "| Topic | Answer |\n| --- | --- |\n| Registration | Open |"
    );

    expect(container.querySelector("table")).not.toBeNull();
    expect(container.querySelector(".md-table-wrapper")).not.toBeNull();
    expect(container.querySelectorAll("th")).toHaveLength(2);
  });

  it("does not create clickable unsafe protocol links", () => {
    const { container } = renderAssistant(
      "[unsafe](javascript:alert(1)) [safe](https://example.com)"
    );

    expect(container.querySelector('a[href^="javascript:"]')).toBeNull();
    expect(container.querySelector('a[href="https://example.com/"]')).not.toBeNull();
  });

  it("does not inject raw HTML or event handlers", () => {
    const { container } = renderAssistant('<img src=x onerror="alert(1)" />');

    expect(container.querySelector("img")).toBeNull();
    expect(container.querySelector("[onerror]")).toBeNull();
  });
});
