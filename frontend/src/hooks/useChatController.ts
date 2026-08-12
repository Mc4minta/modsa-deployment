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
import type { ChatListItem, ChatRecord, Message, Source, StorageErrorInfo } from "../types";

function stripMarkdown(text: string): string {
  return text
    .replace(/```[\s\S]*?```/g, " ")
    .replace(/`([^`]*)`/g, "$1")
    .replace(/!\[([^\]]*)\]\([^)]*\)/g, "$1")
    .replace(/\[([^\]]*)\]\([^)]*\)/g, "$1")
    .replace(/^\s*#{1,6}\s+/gm, "")
    .replace(/^\s*>\s?/gm, "")
    .replace(/^\s*[-*+]\s+/gm, "")
    .replace(/^\s*\d+\.\s+/gm, "")
    .replace(/(\*\*\*|\*\*|\*|___|__|_|~~)/g, "")
    .replace(/\s+/g, " ")
    .trim();
}

const EMPTY_CHAT = (id: string): ChatRecord => ({
  id,
  messages: [],
  updatedAt: Date.now(),
  title: "New Chat",
  preview: "",
});

interface ActiveRequest {
  requestId: string;
  chatId: string;
  pendingMessageId: string;
  userMessageId: string;
  text: string;
  status: "pending";
}

interface ChatState {
  chatsById: Record<string, ChatRecord>;
  activeChatId: string;
  activeRequests: Record<string, ActiveRequest>;
  unseenChatIds: Record<string, true>;
  storageError: StorageErrorInfo | null;
}

type ChatAction =
  | {
      type: "START_REQUEST";
      requestId: string;
      chatId: string;
      pendingMessageId: string;
      userMessageId: string;
      text: string;
      timestamp: number;
    }
  | {
      type: "REQUEST_SUCCEEDED";
      requestId: string;
      chatId: string;
      messageId: string;
      answer: string;
      sources: Source[];
      timestamp: number;
    }
  | {
      type: "REQUEST_FAILED";
      requestId: string;
      chatId: string;
      messageId: string;
      code: string;
      message: string;
      timestamp: number;
    }
  | {
      type: "CANCEL_REQUEST";
      requestId: string;
      chatId: string;
      messageId: string;
      timestamp: number;
      markStopped: boolean;
      message: string;
    }
  | { type: "NEW_CHAT"; chatId: string }
  | { type: "SELECT_CHAT"; chatId: string }
  | { type: "DELETE_CHAT"; chatId: string; nextChatId: string }
  | { type: "CLEAR_ALL"; chatId: string; error: StorageErrorInfo | null }
  | { type: "STORAGE_ERROR"; error: StorageErrorInfo | null };

function makeInitialState(): ChatState {
  let loaded: Record<string, ChatRecord> = {};
  try {
    loaded = loadChats();
  } catch {
    loaded = {};
  }
  const activeChatId = generateId();
  return {
    chatsById: loaded,
    activeChatId,
    activeRequests: {},
    unseenChatIds: {},
    storageError: getStorageStatus(),
  };
}

function withoutKey<T>(record: Record<string, T>, key: string): Record<string, T> {
  if (!(key in record)) return record;
  const next = { ...record };
  delete next[key];
  return next;
}

function updateChat(
  state: ChatState,
  chatId: string,
  update: ChatRecord | ((current: ChatRecord) => ChatRecord)
): ChatState {
  const current = state.chatsById[chatId] || EMPTY_CHAT(chatId);
  const next = typeof update === "function" ? update(current) : update;
  return {
    ...state,
    chatsById: { ...state.chatsById, [chatId]: next },
  };
}

function updatePendingMessage(messages: Message[], pendingId: string, replacement: Message): Message[] {
  const index = messages.findIndex((message) => message.id === pendingId);
  if (index === -1) return [...messages, replacement];
  const next = messages.slice();
  next[index] = replacement;
  return next;
}

function chatReducer(state: ChatState, action: ChatAction): ChatState {
  switch (action.type) {
    case "START_REQUEST": {
      const chat = state.chatsById[action.chatId] || EMPTY_CHAT(action.chatId);
      const userMessage: Message = {
        id: action.userMessageId,
        role: "user",
        content: action.text,
        timestamp: action.timestamp,
        status: "success",
      };
      const pendingMessage: Message = {
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
        activeRequests: {
          ...state.activeRequests,
          [action.chatId]: {
            requestId: action.requestId,
            chatId: action.chatId,
            pendingMessageId: action.pendingMessageId,
            userMessageId: action.userMessageId,
            text: action.text,
            status: "pending",
          },
        },
        unseenChatIds: withoutKey(state.unseenChatIds, action.chatId),
      };
    }

    case "REQUEST_SUCCEEDED": {
      const request = state.activeRequests[action.chatId];
      if (!request || request.requestId !== action.requestId) return state;
      const chat = state.chatsById[action.chatId];
      if (!chat) return { ...state, activeRequests: withoutKey(state.activeRequests, action.chatId) };
      const assistantMessage: Message = {
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
          preview: stripMarkdown(action.answer).slice(0, 160),
          messages: updatePendingMessage(chat.messages, request.pendingMessageId, assistantMessage),
        }),
        activeRequests: withoutKey(state.activeRequests, action.chatId),
        unseenChatIds:
          action.chatId === state.activeChatId
            ? state.unseenChatIds
            : { ...state.unseenChatIds, [action.chatId]: true },
      };
    }

    case "REQUEST_FAILED": {
      const request = state.activeRequests[action.chatId];
      if (!request || request.requestId !== action.requestId) return state;
      const chat = state.chatsById[action.chatId];
      if (!chat) return { ...state, activeRequests: withoutKey(state.activeRequests, action.chatId) };
      const assistantMessage: Message = {
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
        activeRequests: withoutKey(state.activeRequests, action.chatId),
        unseenChatIds:
          action.chatId === state.activeChatId
            ? state.unseenChatIds
            : { ...state.unseenChatIds, [action.chatId]: true },
      };
    }

    case "CANCEL_REQUEST": {
      const request = state.activeRequests[action.chatId];
      if (!request || request.requestId !== action.requestId) return state;
      const chat = state.chatsById[action.chatId];
      if (!chat) return { ...state, activeRequests: withoutKey(state.activeRequests, action.chatId) };
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
        activeRequests: withoutKey(state.activeRequests, action.chatId),
      };
    }

    case "NEW_CHAT":
      return { ...state, activeChatId: action.chatId };

    case "SELECT_CHAT":
      if (!state.chatsById[action.chatId]) return state;
      return {
        ...state,
        activeChatId: action.chatId,
        unseenChatIds: withoutKey(state.unseenChatIds, action.chatId),
      };

    case "DELETE_CHAT": {
      const nextChats = { ...state.chatsById };
      delete nextChats[action.chatId];
      return {
        ...state,
        chatsById: nextChats,
        activeChatId:
          state.activeChatId === action.chatId ? action.nextChatId : state.activeChatId,
        activeRequests: withoutKey(state.activeRequests, action.chatId),
        unseenChatIds: withoutKey(state.unseenChatIds, action.chatId),
      };
    }

    case "CLEAR_ALL":
      return {
        ...state,
        chatsById: {},
        activeChatId: action.chatId,
        activeRequests: {},
        unseenChatIds: {},
        storageError: action.error || null,
      };

    case "STORAGE_ERROR":
      return { ...state, storageError: action.error };

    default:
      return state;
  }
}

function deriveChatList(chatsById: Record<string, ChatRecord>): ChatListItem[] {
  return Object.values(chatsById)
    .filter((chat) => chat.messages.length > 0)
    .sort((a, b) => (b.updatedAt || 0) - (a.updatedAt || 0))
    .map(({ id, title, updatedAt, preview }) => ({ id, title, updatedAt, preview }));
}

function errorMessageFor(error: unknown, fallback: string): string {
  if (error instanceof ApiError && error.code === "VALIDATION") return error.message;
  return fallback;
}

interface UseChatControllerOptions {
  errorMessage?: string;
  stoppedMessage?: string;
}

interface PendingRequestRef {
  requestId: string;
  chatId: string;
  pendingMessageId: string;
  userMessageId: string;
  controller: AbortController;
}

/**
 * Canonical chat/request state. Each chat may have at most one in-flight
 * request; requests keep running in the background when the user navigates
 * away, and their result lands in that chat whenever it resolves.
 */
export function useChatController({ errorMessage = "Something went wrong.", stoppedMessage = "" }: UseChatControllerOptions = {}) {
  const [state, dispatch] = useReducer(chatReducer, undefined, makeInitialState);
  const requestRefs = useRef<Map<string, PendingRequestRef>>(new Map());
  const stateRef = useRef(state);
  stateRef.current = state;
  const lastSavedRef = useRef<Record<string, ChatRecord>>({});

  // Persist any chat whose messages changed and isn't mid-request — including
  // chats resolved in the background while the user was looking elsewhere.
  // Reference-equality against the last-saved object skips unchanged chats
  // cheaply (updateChat always creates a new object for a changed chat and
  // leaves every other chat's reference untouched).
  useEffect(() => {
    Object.values(state.chatsById).forEach((chat) => {
      if (chat.messages.length === 0) return;
      if (state.activeRequests[chat.id]) return;
      if (lastSavedRef.current[chat.id] === chat) return;
      const result = saveChat(chat.id, chat.messages, {
        updatedAt: chat.updatedAt,
        title: chat.title,
        preview: chat.preview,
      });
      if (!result.ok) {
        dispatch({ type: "STORAGE_ERROR", error: result.error });
      } else {
        lastSavedRef.current[chat.id] = chat;
        if (stateRef.current.storageError) dispatch({ type: "STORAGE_ERROR", error: null });
      }
    });
  }, [state.chatsById, state.activeRequests]);

  useEffect(() => () => {
    requestRefs.current.forEach((ref) => ref.controller.abort());
    requestRefs.current.clear();
  }, []);

  const cancelActive = useCallback(
    (chatId: string, { markStopped = false }: { markStopped?: boolean } = {}) => {
      const request = requestRefs.current.get(chatId) || stateRef.current.activeRequests[chatId];
      if (!request) return false;
      requestRefs.current.get(chatId)?.controller.abort();
      requestRefs.current.delete(chatId);
      dispatch({
        type: "CANCEL_REQUEST",
        requestId: request.requestId,
        chatId,
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
    async (text: string) => {
      const trimmed = typeof text === "string" ? text.trim() : "";
      const current = stateRef.current;
      const chatId = current.activeChatId;
      if (!trimmed || current.activeRequests[chatId] || requestRefs.current.has(chatId)) return false;

      const requestId = generateId();
      const pendingMessageId = generateId();
      const userMessageId = generateId();
      const controller = new AbortController();
      requestRefs.current.set(chatId, { requestId, chatId, pendingMessageId, userMessageId, controller });
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
        const apiError = error instanceof ApiError ? error : null;
        if (apiError?.code === "ABORT" || (error as { name?: string })?.name === "AbortError") return false;
        dispatch({
          type: "REQUEST_FAILED",
          requestId,
          chatId,
          messageId: generateId(),
          code: apiError?.code || "UNKNOWN",
          message: errorMessageFor(error, errorMessage),
          timestamp: Date.now(),
        });
        return false;
      } finally {
        if (requestRefs.current.get(chatId)?.requestId === requestId) requestRefs.current.delete(chatId);
      }
    },
    [errorMessage]
  );

  const handleStop = useCallback(
    () => cancelActive(stateRef.current.activeChatId, { markStopped: true }),
    [cancelActive]
  );

  const handleRetry = useCallback(
    (question: string) => handleSend(question),
    [handleSend]
  );

  const handleNewChat = useCallback(() => {
    dispatch({ type: "NEW_CHAT", chatId: generateId() });
  }, []);

  const handleSelectChat = useCallback((chatId: string) => {
    if (!stateRef.current.chatsById[chatId]) return;
    dispatch({ type: "SELECT_CHAT", chatId });
  }, []);

  const handleDeleteChat = useCallback((chatId: string) => {
    const current = stateRef.current;
    requestRefs.current.get(chatId)?.controller.abort();
    requestRefs.current.delete(chatId);
    const deleteResult = deleteStoredChat(chatId);
    if (!deleteResult.ok) dispatch({ type: "STORAGE_ERROR", error: deleteResult.error });
    const remaining = Object.values(current.chatsById)
      .filter((chat) => chat.id !== chatId)
      .sort((a, b) => (b.updatedAt || 0) - (a.updatedAt || 0));
    const nextChatId =
      current.activeChatId === chatId ? remaining[0]?.id || generateId() : current.activeChatId;
    dispatch({ type: "DELETE_CHAT", chatId, nextChatId });
  }, []);

  const handleClearHistory = useCallback(() => {
    requestRefs.current.forEach((ref) => ref.controller.abort());
    requestRefs.current.clear();
    const result = clearAllChats();
    if (!result.ok) {
      dispatch({ type: "STORAGE_ERROR", error: result.error });
      return false;
    }
    dispatch({ type: "CLEAR_ALL", chatId: generateId(), error: null });
    return true;
  }, []);

  const activeChat = state.chatsById[state.activeChatId] || EMPTY_CHAT(state.activeChatId);
  return {
    messages: activeChat.messages,
    isLoading: Boolean(state.activeRequests[state.activeChatId]),
    activeSessionId: state.activeChatId,
    chatList: deriveChatList(state.chatsById),
    loadingChatIds: Object.keys(state.activeRequests),
    unseenChatIds: Object.keys(state.unseenChatIds),
    storageError: state.storageError,
    request: state.activeRequests[state.activeChatId] || null,
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
