import { beforeEach, describe, expect, it } from "vitest";
import {
  clearAllChats,
  generateId,
  getChatList,
  loadChat,
  saveChat,
} from "./storage";

describe("chat storage", () => {
  beforeEach(() => {
    localStorage.clear();
  });

  it("survives corrupted and null legacy storage", () => {
    localStorage.setItem("modsa-chats", "null");
    expect(getChatList()).toEqual([]);
    localStorage.setItem("modsa-chats", "{not-json");
    expect(getChatList()).toEqual([]);
  });

  it("stores a bounded, readable conversation", () => {
    const id = generateId();
    saveChat(id, [
      {
        id: "q1",
        role: "user",
        content: "ทุนมีอะไรบ้าง",
        timestamp: Date.now(),
        status: "complete",
      },
    ]);

    expect(getChatList()).toHaveLength(1);
    expect(loadChat(id)[0]).toMatchObject({
      role: "user",
      content: "ทุนมีอะไรบ้าง",
    });
  });

  it("clears current and legacy storage", () => {
    localStorage.setItem("modsa-chats", "{}");
    clearAllChats();
    expect(localStorage.getItem("modsa-chats")).toBeNull();
    expect(localStorage.getItem("modsa-chats-v2")).toBeNull();
  });
});
