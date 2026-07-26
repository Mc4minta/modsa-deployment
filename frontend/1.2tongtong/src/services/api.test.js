import { afterEach, describe, expect, it, vi } from "vitest";
import { ApiError, askQuestion, cancelRequest } from "./api";

afterEach(() => {
  cancelRequest();
  vi.useRealTimers();
  vi.restoreAllMocks();
});

function abortablePendingFetch(_url, options) {
  return new Promise((_resolve, reject) => {
    options.signal.addEventListener("abort", () => {
      reject(new DOMException("Aborted", "AbortError"));
    });
  });
}

describe("askQuestion", () => {
  it("normalizes the response and rejects unsafe source URLs", async () => {
    vi.spyOn(window, "fetch").mockResolvedValue(
      new Response(
        JSON.stringify({
          answer: "Verified answer",
          confidence: "high",
          sources: [
            {
              title: "Unsafe",
              source: "unsafe.json",
              url: "javascript:alert(1)",
            },
          ],
        }),
        { status: 200, headers: { "Content-Type": "application/json" } },
      ),
    );

    const result = await askQuestion("Question");
    expect(result.sources[0].url).toBeUndefined();
    expect(result.answer).toBe("Verified answer");
  });

  it("rejects an empty or malformed answer", async () => {
    vi.spyOn(window, "fetch").mockResolvedValue(
      new Response(JSON.stringify({ answer: "", sources: [] }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );

    await expect(askQuestion("Question")).rejects.toMatchObject({
      name: "ApiError",
      code: "invalid_response",
    });
  });

  it("maps rate limiting to an actionable error code", async () => {
    vi.spyOn(window, "fetch").mockResolvedValue(
      new Response(JSON.stringify({ detail: "Wait" }), {
        status: 429,
        headers: { "Content-Type": "application/json" },
      }),
    );

    await expect(askQuestion("Question")).rejects.toEqual(
      expect.objectContaining({
        constructor: ApiError,
        code: "rate_limited",
        status: 429,
      }),
    );
  });

  it("maps manual cancellation without racing the active controller", async () => {
    vi.spyOn(window, "fetch").mockImplementation(abortablePendingFetch);
    const pending = askQuestion("Question");
    const assertion = expect(pending).rejects.toMatchObject({ code: "cancelled" });

    cancelRequest();

    await assertion;
  });

  it("maps the request deadline to a timeout error", async () => {
    vi.useFakeTimers();
    vi.spyOn(window, "fetch").mockImplementation(abortablePendingFetch);
    const pending = askQuestion("Question");
    const assertion = expect(pending).rejects.toMatchObject({ code: "timeout" });

    await vi.advanceTimersByTimeAsync(45_000);

    await assertion;
  });
});
