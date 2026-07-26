import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { LanguageProvider } from "../i18n/LanguageProvider";
import { MessageBubble } from "./MessageBubble";

function renderMessage(message) {
  return render(
    <LanguageProvider>
      <MessageBubble message={message} onRetry={() => {}} />
    </LanguageProvider>,
  );
}

const baseMessage = {
  id: "answer-1",
  role: "assistant",
  confidence: "high",
  timestamp: Date.now(),
  status: "complete",
};

describe("MessageBubble", () => {
  it("renders GFM tables with accessible column headers", () => {
    renderMessage({
      ...baseMessage,
      content: "| Date | Action |\n| --- | --- |\n| 1 Aug | Register |",
      sources: [{ source: "calendar.json", title: "Calendar", page: 1 }],
    });

    expect(screen.getByRole("table")).toBeInTheDocument();
    expect(screen.getByRole("columnheader", { name: "Date" })).toHaveAttribute(
      "scope",
      "col",
    );
  });

  it("does not create an executable unsafe link", () => {
    renderMessage({
      ...baseMessage,
      content: "[unsafe](javascript:alert(1)) <script>alert(2)</script>",
      sources: [],
    });

    expect(screen.queryByRole("link", { name: "unsafe" })).not.toBeInTheDocument();
    expect(document.querySelector("script")).toBeNull();
  });

  it("fails closed when no supporting sources were returned", () => {
    renderMessage({
      ...baseMessage,
      content: "An answer without evidence.",
      sources: [],
    });

    expect(
      screen.getByText("Not verified from the knowledge base"),
    ).toBeInTheDocument();
    expect(screen.queryByText("Multiple sources retrieved")).not.toBeInTheDocument();
  });
});
