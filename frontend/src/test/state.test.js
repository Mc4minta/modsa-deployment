import { describe, expect, it } from "vitest";
import { chatReducer, deriveChatList } from "../hooks/useChatController";

function stateWithChat(chatId = "chat-a") {
  return {
    chatsById: {
      [chatId]: {
        id: chatId,
        messages: [],
        updatedAt: 1,
        title: "New Chat",
        preview: "",
      },
    },
    activeChatId: chatId,
    activeRequest: null,
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
    expect(started.chatsById["chat-a"].messages.at(-1).status).toBe("pending");
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
      sources: [{ title: "Handbook" }],
      timestamp: 3,
    });

    expect(finished.activeRequest).toBeNull();
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

    expect(stopped.activeRequest).toBeNull();
    expect(stopped.chatsById["chat-a"].messages.at(-1)).toMatchObject({
      status: "stopped",
      content: "Stopped",
    });
    expect(stopped.chatsById["chat-b"].messages).toEqual([]);
  });

  it("derives sidebar summaries from chats with messages", () => {
    const list = deriveChatList({
      empty: { id: "empty", messages: [], updatedAt: 20, title: "Empty", preview: "" },
      old: { id: "old", messages: [{ id: "m1" }], updatedAt: 10, title: "Old", preview: "one" },
      recent: {
        id: "recent",
        messages: [{ id: "m2" }],
        updatedAt: 30,
        title: "Recent",
        preview: "two",
      },
    });

    expect(list.map(({ id }) => id)).toEqual(["recent", "old"]);
    expect(list[0]).toEqual({ id: "recent", title: "Recent", updatedAt: 30, preview: "two" });
  });

  it("removes an abandoned user turn when navigation cancels a request", () => {
    const started = chatReducer(stateWithChat(), {
      type: "START_REQUEST",
      requestId: "request-a",
      chatId: "chat-a",
      pendingMessageId: "pending-a",
      userMessageId: "user-a",
      text: "Question A",
      timestamp: 2,
    });

    const cancelled = chatReducer(started, {
      type: "CANCEL_REQUEST",
      requestId: "request-a",
      chatId: "chat-a",
      messageId: "cancelled-a",
      timestamp: 3,
      markStopped: false,
    });

    expect(cancelled.chatsById["chat-a"].messages).toEqual([]);
  });
});
