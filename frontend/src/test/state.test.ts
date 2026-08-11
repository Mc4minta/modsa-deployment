import { describe, expect, it } from "vitest";
import { chatReducer, deriveChatList } from "../hooks/useChatController";
import type { ChatRecord, Source } from "../types";

function stateWithChat(chatId = "chat-a") {
  return {
    chatsById: {
      [chatId]: {
        id: chatId,
        messages: [],
        updatedAt: 1,
        title: "New Chat",
        preview: "",
      } as ChatRecord,
    },
    activeChatId: chatId,
    activeRequests: {},
    unseenChatIds: {},
    storageError: null,
  };
}

describe("chat state ownership", () => {
  it("ignores a late result when request or chat identity does not match", () => {
    const started = chatReducer(stateWithChat(), {
      type: "START_REQUEST",
      requestId: "request-a",
      chatId: "chat-a",
      pendingMessageId: "pending-a",
      userMessageId: "user-a",
      text: "Question A",
      timestamp: 2,
    });

    const stale = chatReducer(started, {
      type: "REQUEST_SUCCEEDED",
      requestId: "request-old",
      chatId: "chat-a",
      messageId: "answer-old",
      answer: "stale",
      sources: [],
      timestamp: 3,
    });
    expect(stale).toBe(started);

    const wrongChat = chatReducer(started, {
      type: "REQUEST_SUCCEEDED",
      requestId: "request-a",
      chatId: "chat-b",
      messageId: "answer-wrong-chat",
      answer: "wrong room",
      sources: [],
      timestamp: 3,
    });
    expect(wrongChat).toBe(started);
    expect(started.chatsById["chat-a"].messages.at(-1)?.status).toBe("pending");
  });

  it("replaces only the matching pending message on success", () => {
    const started = chatReducer(stateWithChat(), {
      type: "START_REQUEST",
      requestId: "request-a",
      chatId: "chat-a",
      pendingMessageId: "pending-a",
      userMessageId: "user-a",
      text: "Question A",
      timestamp: 2,
    });

    const finished = chatReducer(started, {
      type: "REQUEST_SUCCEEDED",
      requestId: "request-a",
      chatId: "chat-a",
      messageId: "answer-a",
      answer: "Answer A",
      sources: [{ title: "Handbook" }] as unknown as Source[],
      timestamp: 3,
    });

    expect(finished.activeRequests["chat-a"]).toBeUndefined();
    expect(finished.chatsById["chat-a"].messages).toHaveLength(2);
    expect(finished.chatsById["chat-a"].messages[1]).toMatchObject({
      id: "answer-a",
      content: "Answer A",
      status: "success",
    });
  });

  it("cancels a matching request and marks it stopped without touching another chat", () => {
    const started = chatReducer(
      {
        ...stateWithChat(),
        chatsById: {
          ...stateWithChat().chatsById,
          "chat-b": {
            id: "chat-b",
            messages: [],
            updatedAt: 1,
            title: "Other",
            preview: "",
          },
        },
      },
      {
        type: "START_REQUEST",
        requestId: "request-a",
        chatId: "chat-a",
        pendingMessageId: "pending-a",
        userMessageId: "user-a",
        text: "Question A",
        timestamp: 2,
      }
    );

    const stopped = chatReducer(started, {
      type: "CANCEL_REQUEST",
      requestId: "request-a",
      chatId: "chat-a",
      messageId: "stopped-a",
      message: "Stopped",
      timestamp: 3,
      markStopped: true,
    });

    expect(stopped.activeRequests["chat-a"]).toBeUndefined();
    expect(stopped.chatsById["chat-a"].messages.at(-1)).toMatchObject({
      status: "stopped",
      content: "Stopped",
    });
    expect(stopped.chatsById["chat-b"].messages).toEqual([]);
  });

  it("derives sidebar summaries from chats with messages", () => {
    const list = deriveChatList({
      empty: { id: "empty", messages: [], updatedAt: 20, title: "Empty", preview: "" },
      old: { id: "old", messages: [{ id: "m1" }], updatedAt: 10, title: "Old", preview: "one" } as unknown as ChatRecord,
      recent: {
        id: "recent",
        messages: [{ id: "m2" }],
        updatedAt: 30,
        title: "Recent",
        preview: "two",
      } as unknown as ChatRecord,
    });

    expect(list.map(({ id }) => id)).toEqual(["recent", "old"]);
    expect(list[0]).toEqual({ id: "recent", title: "Recent", updatedAt: 30, preview: "two" });
  });

  it("leaves an in-flight request untouched when navigating to another chat", () => {
    const withChatB = {
      ...stateWithChat(),
      chatsById: {
        ...stateWithChat().chatsById,
        "chat-b": { id: "chat-b", messages: [], updatedAt: 1, title: "Other", preview: "" },
      },
    };
    const started = chatReducer(withChatB, {
      type: "START_REQUEST",
      requestId: "request-a",
      chatId: "chat-a",
      pendingMessageId: "pending-a",
      userMessageId: "user-a",
      text: "Question A",
      timestamp: 2,
    });

    const navigated = chatReducer(started, { type: "SELECT_CHAT", chatId: "chat-b" });

    expect(navigated.activeChatId).toBe("chat-b");
    expect(navigated.activeRequests["chat-a"]).toEqual(started.activeRequests["chat-a"]);
    expect(navigated.chatsById["chat-a"].messages).toEqual(started.chatsById["chat-a"].messages);
  });

  it("marks a background success as unseen and delivers it when the chat is later opened", () => {
    const withChatB = {
      ...stateWithChat(),
      chatsById: {
        ...stateWithChat().chatsById,
        "chat-b": { id: "chat-b", messages: [], updatedAt: 1, title: "Other", preview: "" },
      },
    };
    const started = chatReducer(withChatB, {
      type: "START_REQUEST",
      requestId: "request-a",
      chatId: "chat-a",
      pendingMessageId: "pending-a",
      userMessageId: "user-a",
      text: "Question A",
      timestamp: 2,
    });
    const navigated = chatReducer(started, { type: "SELECT_CHAT", chatId: "chat-b" });

    const resolved = chatReducer(navigated, {
      type: "REQUEST_SUCCEEDED",
      requestId: "request-a",
      chatId: "chat-a",
      messageId: "answer-a",
      answer: "Answer A",
      sources: [],
      timestamp: 3,
    });

    expect(resolved.activeRequests["chat-a"]).toBeUndefined();
    expect(resolved.unseenChatIds["chat-a"]).toBe(true);
    expect(resolved.chatsById["chat-a"].messages[1]).toMatchObject({ status: "success", content: "Answer A" });
    expect(resolved.activeChatId).toBe("chat-b");

    const reopened = chatReducer(resolved, { type: "SELECT_CHAT", chatId: "chat-a" });
    expect(reopened.unseenChatIds["chat-a"]).toBeUndefined();
  });

  it("does not mark a foreground success as unseen", () => {
    const started = chatReducer(stateWithChat(), {
      type: "START_REQUEST",
      requestId: "request-a",
      chatId: "chat-a",
      pendingMessageId: "pending-a",
      userMessageId: "user-a",
      text: "Question A",
      timestamp: 2,
    });
    const resolved = chatReducer(started, {
      type: "REQUEST_SUCCEEDED",
      requestId: "request-a",
      chatId: "chat-a",
      messageId: "answer-a",
      answer: "Answer A",
      sources: [],
      timestamp: 3,
    });
    expect(resolved.unseenChatIds["chat-a"]).toBeUndefined();
  });

  it("allows two chats to have independent in-flight requests at once", () => {
    const withChatB = {
      ...stateWithChat(),
      chatsById: {
        ...stateWithChat().chatsById,
        "chat-b": { id: "chat-b", messages: [], updatedAt: 1, title: "Other", preview: "" },
      },
    };
    const startedA = chatReducer(withChatB, {
      type: "START_REQUEST",
      requestId: "request-a",
      chatId: "chat-a",
      pendingMessageId: "pending-a",
      userMessageId: "user-a",
      text: "Question A",
      timestamp: 2,
    });
    const startedBoth = chatReducer(startedA, {
      type: "START_REQUEST",
      requestId: "request-b",
      chatId: "chat-b",
      pendingMessageId: "pending-b",
      userMessageId: "user-b",
      text: "Question B",
      timestamp: 3,
    });

    expect(Object.keys(startedBoth.activeRequests).sort()).toEqual(["chat-a", "chat-b"]);
    expect(startedBoth.chatsById["chat-a"].messages).toHaveLength(2);
    expect(startedBoth.chatsById["chat-b"].messages).toHaveLength(2);
  });

  it("stopping one chat's request does not affect another chat's in-flight request", () => {
    const withChatB = {
      ...stateWithChat(),
      chatsById: {
        ...stateWithChat().chatsById,
        "chat-b": { id: "chat-b", messages: [], updatedAt: 1, title: "Other", preview: "" },
      },
    };
    const startedA = chatReducer(withChatB, {
      type: "START_REQUEST",
      requestId: "request-a",
      chatId: "chat-a",
      pendingMessageId: "pending-a",
      userMessageId: "user-a",
      text: "Question A",
      timestamp: 2,
    });
    const startedBoth = chatReducer(startedA, {
      type: "START_REQUEST",
      requestId: "request-b",
      chatId: "chat-b",
      pendingMessageId: "pending-b",
      userMessageId: "user-b",
      text: "Question B",
      timestamp: 3,
    });

    const stoppedA = chatReducer(startedBoth, {
      type: "CANCEL_REQUEST",
      requestId: "request-a",
      chatId: "chat-a",
      messageId: "stopped-a",
      message: "Stopped",
      timestamp: 4,
      markStopped: true,
    });

    expect(stoppedA.activeRequests["chat-a"]).toBeUndefined();
    expect(stoppedA.chatsById["chat-a"].messages.at(-1)).toMatchObject({ status: "stopped" });
    expect(stoppedA.activeRequests["chat-b"]).toEqual(startedBoth.activeRequests["chat-b"]);
    expect(stoppedA.chatsById["chat-b"].messages.at(-1)?.status).toBe("pending");
  });

  it("purges a deleted chat's in-flight request and unseen flag", () => {
    const started = chatReducer(stateWithChat(), {
      type: "START_REQUEST",
      requestId: "request-a",
      chatId: "chat-a",
      pendingMessageId: "pending-a",
      userMessageId: "user-a",
      text: "Question A",
      timestamp: 2,
    });

    const deleted = chatReducer(started, {
      type: "DELETE_CHAT",
      chatId: "chat-a",
      nextChatId: "chat-new",
    });

    expect(deleted.chatsById["chat-a"]).toBeUndefined();
    expect(deleted.activeRequests["chat-a"]).toBeUndefined();
    expect(deleted.unseenChatIds["chat-a"]).toBeUndefined();
  });

  it("CLEAR_ALL empties activeRequests and unseenChatIds", () => {
    const withChatB = {
      ...stateWithChat(),
      chatsById: {
        ...stateWithChat().chatsById,
        "chat-b": { id: "chat-b", messages: [], updatedAt: 1, title: "Other", preview: "" },
      },
    };
    const started = chatReducer(withChatB, {
      type: "START_REQUEST",
      requestId: "request-a",
      chatId: "chat-a",
      pendingMessageId: "pending-a",
      userMessageId: "user-a",
      text: "Question A",
      timestamp: 2,
    });

    const cleared = chatReducer(started, { type: "CLEAR_ALL", chatId: "chat-new", error: null });

    expect(cleared.activeRequests).toEqual({});
    expect(cleared.unseenChatIds).toEqual({});
  });
});
