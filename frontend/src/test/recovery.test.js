import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { askQuestion } from "../services/api";
import {
  getStorageStatus,
  loadChats,
  resetStorageStatus,
  saveChat,
} from "../utils/storage";

function response(body, status = 200) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "content-type": "application/json" },
  });
}

describe("request and persistence recovery", () => {
  beforeEach(() => {
    vi.stubGlobal("fetch", vi.fn());
    window.localStorage.clear();
    resetStorageStatus();
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
    vi.useRealTimers();
  });

  it("supports retrying a failed request with a fresh API call", async () => {
    fetch
      .mockResolvedValueOnce(response({ detail: "temporary outage" }, 500))
      .mockResolvedValueOnce(response({ answer: "Recovered", sources: [] }));

    await expect(askQuestion("retry me")).rejects.toMatchObject({ code: "SERVER" });
    await expect(askQuestion("retry me")).resolves.toEqual({
      answer: "Recovered",
      sources: [],
    });
    expect(fetch).toHaveBeenCalledTimes(2);
  });

  it("maps timeout to a recoverable error and permits a later success", async () => {
    vi.useFakeTimers();
    fetch.mockImplementationOnce((_, options) => new Promise((resolve, reject) => {
      options.signal.addEventListener("abort", () => {
        reject(Object.assign(new Error("aborted"), { name: "AbortError" }));
      });
      void resolve;
    }));

    const timedOut = expect(
      askQuestion("slow", { timeoutMs: 10 })
    ).rejects.toMatchObject({ code: "TIMEOUT" });
    await vi.advanceTimersByTimeAsync(11);
    await timedOut;

    fetch.mockResolvedValueOnce(response({ answer: "Fast answer", sources: [] }));
    await expect(askQuestion("slow")).resolves.toMatchObject({ answer: "Fast answer" });
  });

  it("recovers from one quota failure when storage becomes writable", () => {
    const setItem = vi.spyOn(Storage.prototype, "setItem");
    setItem.mockImplementationOnce(() => {
      throw new DOMException("quota", "QuotaExceededError");
    });

    const failed = saveChat("recoverable", [
      { id: "m1", role: "user", content: "first", status: "success", timestamp: 1 },
    ]);
    expect(failed).toMatchObject({ ok: false, error: { code: "QUOTA" } });
    expect(getStorageStatus()).toMatchObject({ code: "QUOTA" });

    setItem.mockRestore();
    const recovered = saveChat("recoverable", [
      { id: "m2", role: "assistant", content: "saved", status: "success", timestamp: 2 },
    ]);
    expect(recovered).toMatchObject({ ok: true });
    expect(loadChats().recoverable.messages[0].content).toBe("saved");
  });
});
