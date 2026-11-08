import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import {
  ApiError,
  askQuestion,
  normalizeChatResponse,
  normalizeSource,
} from "../services/api";

function jsonResponse(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "content-type": "application/json" },
  });
}

let fetchMock: ReturnType<typeof vi.fn>;

describe("chat API contract", () => {
  beforeEach(() => {
    fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    vi.useRealTimers();
  });

  it("normalizes answers and removes unsafe or empty sources", () => {
    const result = normalizeChatResponse({
      answer: "Grounded answer",
      sources: [
        { title: "Handbook", url: "https://example.com/handbook" },
        { title: "Unsafe", url: "javascript:alert(1)" },
        null,
        {},
      ],
    });

    expect(result).toEqual({
      answer: "Grounded answer",
      sources: [
        {
          title: "Handbook",
          source: "",
          department: "",
          page: "",
          url: "https://example.com/handbook",
          id: "source-1",
        },
        {
          title: "Unsafe",
          source: "",
          department: "",
          page: "",
          url: "",
          id: "source-2",
        },
      ],
    });
    expect(normalizeSource({ title: "", source: "" })).toBeNull();
  });

  it("rejects malformed successful responses", () => {
    expect(() => normalizeChatResponse({ sources: [] })).toThrowError(ApiError);
    expect(() => normalizeChatResponse({ answer: "ok", sources: {} })).toThrowError(
      expect.objectContaining({ code: "MALFORMED" })
    );
  });

  it.each([
    [422, "VALIDATION"],
    [429, "RATE_LIMIT"],
    [500, "SERVER"],
  ])("maps HTTP %s to a typed error", async (status: number, code: string) => {
    fetchMock.mockResolvedValue(jsonResponse({ detail: `error-${status}` }, status));

    await expect(askQuestion("question")).rejects.toMatchObject({ code, status });
    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining("/chat/ask"),
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({ question: "question" }),
      })
    );
  });

  it("does not send the optional ngrok header by default", async () => {
    fetchMock.mockResolvedValue(jsonResponse({ answer: "ok", sources: [] }));

    await askQuestion("question");

    const [, options] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(options.headers).toEqual({ "Content-Type": "application/json" });
  });

  it("sends the optional ngrok header on chat and health when enabled", async () => {
    vi.stubEnv("VITE_NGROK_SKIP_BROWSER_WARNING", "true");
    vi.resetModules();
    const api = await import("../services/api");
    fetchMock
      .mockResolvedValueOnce(jsonResponse({ answer: "ok", sources: [] }))
      .mockResolvedValueOnce(new Response("", { status: 200 }));

    await api.askQuestion("question");
    await api.checkHealth();

    expect(fetchMock.mock.calls[0][1].headers).toEqual({
      "Content-Type": "application/json",
      "ngrok-skip-browser-warning": "1",
    });
    expect(fetchMock.mock.calls[1][1].headers).toEqual({
      "ngrok-skip-browser-warning": "1",
    });
  });

  it("maps caller cancellation to ABORT and timeout to TIMEOUT", async () => {
    fetchMock.mockImplementation((_: RequestInfo | URL, options: RequestInit & { signal: AbortSignal }) => new Promise((resolve, reject) => {
      options.signal.addEventListener("abort", () => {
        reject(Object.assign(new Error("aborted"), { name: "AbortError" }));
      });
      void resolve;
    }));

    const caller = new AbortController();
    const cancelled = askQuestion("cancel me", { signal: caller.signal, timeoutMs: 100 });
    caller.abort();
    await expect(cancelled).rejects.toMatchObject({ code: "ABORT" });

    vi.useFakeTimers();
    const timedOut = expect(
      askQuestion("time out", { timeoutMs: 5 })
    ).rejects.toMatchObject({ code: "TIMEOUT" });
    await vi.advanceTimersByTimeAsync(6);
    await timedOut;
  });
});
