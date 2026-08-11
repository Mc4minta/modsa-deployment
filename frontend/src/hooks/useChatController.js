import { useCallback, useEffect, useReducer, useRef } from "react";
import { askQuestion, ApiError } from "../services/api";
import {
  deleteChat as deleteStoredChat,
  clearAllChats,
  generateId,
  getStorageStatus,
  loadChats,
  saveChat,
} from "../utils/storage";

const EMPTY_CHAT = (id) => ({
  id,
  messages: [],
  updatedAt: Date.now(),
  title: "New Chat",
  preview: "",
});

function makeInitialState() {
  let loaded = {};
  try {
    loaded = loadChats();
  } catch {
    loaded = {};
  }
  const activeChatId = generateId();
  return {
    chatsById: loaded,
    activeChatId,
    activeRequest: null,
    storageError: getStorageStatus(),
  };
}

function updateChat(state, chatId, update) {
  const current = state.chatsById[chatId] || EMPTY_CHAT(chatId);
  const next = typeof update === "function" ? update(current) : update;
  return {
    ...state,
    chatsById: { ...state.chatsById, [chatId]: next },
  };
}

function updatePendingMessage(messages, pendingId, replacement) {
  const index = messages.findIndex((message) => message.id === pendingId);
  if (index === -1) return [...messages, replacement];
  const next = messages.slice();
  next[index] = replacement;
  return next;
}

function chatReducer(state, action) {
  switch (action.type) {
    case "START_REQUEST": {
      const chat = state.chatsById[action.chatId] || EMPTY_CHAT(action.chatId);
      const userMessage = {
        id: action.userMessageId,
        role: "user",
        content: action.text,
        timestamp: action.timestamp,
        status: "success",
      };
      const pendingMessage = {
        id: action.pendingMessageId,
        role: "assistant",
        content: "",
        timestamp: action.timestamp,
        status: "pending",
        sources: [],
      };
      return {
        ...updateChat(state, action.chatId, {
          ...chat,
          updatedAt: action.timestamp,
          title:
            chat.title === "New Chat"
              ? action.text.trim().slice(0, 80) || "New Chat"
              : chat.title,
          messages: [...chat.messages, userMessage, pendingMessage],
        }),
        activeChatId: action.chatId,
        activeRequest: {
          requestId: action.requestId,
          chatId: action.chatId,
          pendingMessageId: action.pendingMessageId,
          userMessageId: action.userMessageId,
          text: action.text,
          status: "pending",
        },
      };
    }

    case "REQUEST_SUCCEEDED": {
      const request = state.activeRequest;
      if (!request || request.requestId !== action.requestId || request.chatId !== action.chatId) {
        return state;
      }
      const chat = state.chatsById[action.chatId];
      if (!chat) return { ...state, activeRequest: null };
      const assistantMessage = {
        id: action.messageId,
        role: "assistant",
        content: action.answer,
        sources: action.sources,
        timestamp: action.timestamp,
        status: "success",
      };
      return {
        ...updateChat(state, action.chatId, {
          ...chat,
          updatedAt: action.timestamp,
          preview: action.answer.slice(0, 160),
          messages: updatePendingMessage(chat.messages, request.pendingMessageId, assistantMessage),
        }),
        activeRequest: null,
      };
    }

    case "REQUEST_FAILED": {
      const request = state.activeRequest;
      if (!request || request.requestId !== action.requestId || request.chatId !== action.chatId) {
        return state;
      }
      const chat = state.chatsById[action.chatId];
      if (!chat) return { ...state, activeRequest: null };
      const assistantMessage = {
        id: action.messageId,
        role: "assistant",
        content: action.message,
        sources: [],
        timestamp: action.timestamp,
        status: "error",
        errorCode: action.code,
        originalQuestion: request.text,
      };
      return {
        ...updateChat(state, action.chatId, {
          ...chat,
          updatedAt: action.timestamp,
          preview: action.message.slice(0, 160),
          messages: updatePendingMessage(chat.messages, request.pendingMessageId, assistantMessage),
        }),
        activeRequest: null,
      };
    }

    case "CANCEL_REQUEST": {
      const request = state.activeRequest;
      if (!request || request.requestId !== action.requestId || request.chatId !== action.chatId) {
        return state;
      }
      const chat = state.chatsById[action.chatId];
      if (!chat) return { ...state, activeRequest: null };
      const messages = action.markStopped
        ? updatePendingMessage(chat.messages, request.pendingMessageId, {
            id: action.messageId,
            role: "assistant",
            content: action.message || "",
            sources: [],
            timestamp: action.timestamp,
            status: "stopped",
            originalQuestion: request.text,
          })
        : chat.messages.filter(
            (message) =>
              message.id !== request.pendingMessageId && message.id !== request.userMessageId
          );
      return {
        ...updateChat(state, action.chatId, {
          ...chat,
          updatedAt: action.timestamp,
          messages,
        }),
        activeRequest: null,
      };
    }

    case "NEW_CHAT":
      return { ...state, activeChatId: action.chatId, activeRequest: null };

    case "SELECT_CHAT":
      if (!state.chatsById[action.chatId]) return state;
      return { ...state, activeChatId: action.chatId, activeRequest: null };

    case "DELETE_CHAT": {
      const nextChats = { ...state.chatsById };
      delete nextChats[action.chatId];
      return {
        ...state,
        chatsById: nextChats,
        activeChatId:
          state.activeChatId === action.chatId ? action.nextChatId : state.activeChatId,
        activeRequest: null,
      };
    }

    case "CLEAR_ALL":
      return {
        ...state,
        chatsById: {},
        activeChatId: action.chatId,
        activeRequest: null,
        storageError: action.error || null,
      };

    case "STORAGE_ERROR":
      return { ...state, storageError: action.error };

    default:
      return state;
  }
}

function deriveChatList(chatsById) {
  return Object.values(chatsById)
    .filter((chat) => chat.messages.length > 0)
    .sort((a, b) => (b.updatedAt || 0) - (a.updatedAt || 0))
    .map(({ id, title, updatedAt, preview }) => ({ id, title, updatedAt, preview }));
}

function errorMessageFor(error, fallback) {
  if (error instanceof ApiError && error.code === "VALIDATION") return error.message;
  return fallback;
}

/**
 * Canonical chat/request state. One request is allowed at a time; its immutable
 * requestId and chatId are checked by the reducer before any result is applied.
 */
export function useChatController({ errorMessage = "Something went wrong.", stoppedMessage = "" } = {}) {
  const [state, dispatch] = useReducer(chatReducer, undefined, makeInitialState);
  const requestRef = useRef(null);
  const stateRef = useRef(state);
  stateRef.current = state;

  useEffect(() => {
    if (state.activeRequest) return;
    for (const chat of Object.values(state.chatsById)) {
      if (chat.messages.length === 0) continue;
      const result = saveChat(chat.id, chat.messages, {
        updatedAt: chat.updatedAt,
        title: chat.title,
        preview: chat.preview,
      });
      if (!result.ok) {
        dispatch({ type: "STORAGE_ERROR", error: result.error });
      } else if (stateRef.current.storageError) {
        dispatch({ type: "STORAGE_ERROR", error: null });
      }
    }
  }, [state.chatsById, state.activeRequest]);

  useEffect(() => () => {
    requestRef.current?.controller.abort();
    requestRef.current = null;
  }, []);

  const cancelActive = useCallback(
    ({ markStopped = false } = {}) => {
      const request = requestRef.current || stateRef.current.activeRequest;
      if (!request) return false;
      requestRef.current?.controller.abort();
      requestRef.current = null;
      dispatch({
        type: "CANCEL_REQUEST",
        requestId: request.requestId,
        chatId: request.chatId,
        messageId: generateId(),
        timestamp: Date.now(),
        markStopped,
        message: stoppedMessage,
      });
      return true;
    },
    [stoppedMessage]
  );

  const handleSend = useCallback(
    async (text) => {
      const trimmed = typeof text === "string" ? text.trim() : "";
      const current = stateRef.current;
      if (!trimmed || current.activeRequest || requestRef.current) return false;

      const chatId = current.activeChatId;
      const requestId = generateId();
      const pendingMessageId = generateId();
      const userMessageId = generateId();
      const controller = new AbortController();
      requestRef.current = { requestId, chatId, pendingMessageId, userMessageId, controller };
      dispatch({
        type: "START_REQUEST",
        requestId,
        chatId,
        pendingMessageId,
        userMessageId,
        text: trimmed,
        timestamp: Date.now(),
      });

      try {
        const data = await askQuestion(trimmed, { signal: controller.signal });
        dispatch({
          type: "REQUEST_SUCCEEDED",
          requestId,
          chatId,
          messageId: generateId(),
          answer: data.answer,
          sources: data.sources,
          timestamp: Date.now(),
        });
        return true;
      } catch (error) {
        if (error?.code === "ABORT" || error?.name === "AbortError") return false;
        dispatch({
          type: "REQUEST_FAILED",
          requestId,
          chatId,
          messageId: generateId(),
          code: error?.code || "UNKNOWN",
          message: errorMessageFor(error, errorMessage),
          timestamp: Date.now(),
        });
        return false;
      } finally {
        if (requestRef.current?.requestId === requestId) requestRef.current = null;
      }
    },
    [errorMessage]
  );

  const handleStop = useCallback(() => cancelActive({ markStopped: true }), [cancelActive]);

  const handleRetry = useCallback(
    (question) => handleSend(question),
    [handleSend]
  );

  const handleNewChat = useCallback(() => {
    cancelActive();
    dispatch({ type: "NEW_CHAT", chatId: generateId() });
  }, [cancelActive]);

  const handleSelectChat = useCallback(
    (chatId) => {
      if (!stateRef.current.chatsById[chatId]) return;
      cancelActive();
      dispatch({ type: "SELECT_CHAT", chatId });
    },
    [cancelActive]
  );

  const handleDeleteChat = useCallback(
    (chatId) => {
      const current = stateRef.current;
      // A single global request is active at most once; deleting any chat
      // cancels it so a late response cannot target a newly selected chat.
      if (current.activeRequest || requestRef.current) cancelActive();
      const deleteResult = deleteStoredChat(chatId);
      if (!deleteResult.ok) dispatch({ type: "STORAGE_ERROR", error: deleteResult.error });
      const remaining = Object.values(current.chatsById)
        .filter((chat) => chat.id !== chatId)
        .sort((a, b) => (b.updatedAt || 0) - (a.updatedAt || 0));
      const nextChatId =
        current.activeChatId === chatId ? remaining[0]?.id || generateId() : current.activeChatId;
      dispatch({ type: "DELETE_CHAT", chatId, nextChatId });
    },
    [cancelActive]
  );

  const handleClearHistory = useCallback(() => {
    cancelActive();
    const result = clearAllChats();
    if (!result.ok) {
      dispatch({ type: "STORAGE_ERROR", error: result.error });
      return false;
    }
    dispatch({ type: "CLEAR_ALL", chatId: generateId(), error: null });
    return true;
  }, [cancelActive]);

  const activeChat = state.chatsById[state.activeChatId] || EMPTY_CHAT(state.activeChatId);
  return {
    messages: activeChat.messages,
    isLoading: Boolean(state.activeRequest),
    activeSessionId: state.activeChatId,
    chatList: deriveChatList(state.chatsById),
    storageError: state.storageError,
    request: state.activeRequest,
    handleSend,
    handleStop,
    handleRetry,
    handleNewChat,
    handleSelectChat,
    handleDeleteChat,
    handleClearHistory,
  };
}

export { chatReducer, deriveChatList, makeInitialState };
