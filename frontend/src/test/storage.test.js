import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import {
  STORAGE_KEY,
  STORAGE_LIMITS,
  clearAllChats,
  getStorageStatus,
  loadChats,
  resetStorageStatus,
  saveChat,
} from "../utils/storage";

function message(id, content = `message ${id}`, role = "assistant") {
  return {
    id,
    role,
    content,
    status: "success",
    timestamp: Number(id.replace(/\D/g, "")) || 1,
  };
}

describe("versioned chat storage", () => {
  beforeEach(() => {
    window.localStorage.clear();
    resetStorageStatus();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("migrates the original unversioned map and filters pending messages", () => {
    window.localStorage.setItem(
      STORAGE_KEY,
      JSON.stringify({
        legacy: {
          messages: [
            message("1", "kept", "user"),
            { ...message("2", "pending"), status: "pending" },
          ],
          title: "Legacy chat",
          updatedAt: 2,
        },
      })
    );

    const chats = loadChats();
    expect(chats.legacy.title).toBe("Legacy chat");
    expect(chats.legacy.messages).toHaveLength(1);
    expect(chats.legacy.messages[0].content).toBe("kept");
  });

  it("recovers from corrupt JSON instead of throwing", () => {
    window.localStorage.setItem(STORAGE_KEY, "{not-json");

    expect(loadChats()).toEqual({});
    expect(getStorageStatus()).toMatchObject({ code: "CORRUPT" });
    expect(window.localStorage.getItem(STORAGE_KEY)).toBeNull();
  });

  it("bounds persisted chats and message content", () => {
    const longText = "x".repeat(STORAGE_LIMITS.maxMessageChars + 500);
    const chats = {};
    for (let index = 0; index < STORAGE_LIMITS.maxChats + 3; index += 1) {
      const id = `chat-${index}`;
      chats[id] = {
        id,
        title: id,
        updatedAt: index + 1,
        messages: [message(`${index + 1}`, longText)],
      };
    }
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(chats));

    expect(saveChat("new-chat", [message("999", longText)])).toMatchObject({ ok: true });
    const saved = loadChats();
    expect(Object.keys(saved).length).toBeLessThanOrEqual(STORAGE_LIMITS.maxChats);
    expect(saved["new-chat"].messages[0].content).toHaveLength(
      STORAGE_LIMITS.maxMessageChars
    );
  });

  it("reports quota failures without crashing the caller", () => {
    vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => {
      throw new DOMException("quota", "QuotaExceededError");
    });

    const result = saveChat("quota-chat", [message("1")]);
    expect(result.ok).toBe(false);
    expect(result.error).toMatchObject({ code: "QUOTA" });
    expect(getStorageStatus()).toMatchObject({ code: "QUOTA" });
  });

  it("clears history through the storage adapter", () => {
    saveChat("chat", [message("1")]);
    expect(clearAllChats()).toMatchObject({ ok: true });
    expect(loadChats()).toEqual({});
  });
});
