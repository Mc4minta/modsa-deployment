import type { ChatMetadata, ChatRecord, ChatListItem, Message, Source, StorageErrorInfo, StorageResult } from "../types";

const STORAGE_KEY = "modsa-chats";
export const STORAGE_VERSION = 1;
export const STORAGE_LIMITS = Object.freeze({
  maxChats: 50,
  maxMessagesPerChat: 100,
  maxMessageChars: 20_000,
  maxTotalChars: 500_000,
});

const VALID_ROLES = new Set(["user", "assistant"]);
const VALID_STATUSES = new Set(["pending", "success", "error", "stopped"]);
let lastStorageError: StorageErrorInfo | null = null;

function setStorageError(code: string, message: string): void {
  lastStorageError = { code, message, at: Date.now() };
}

function getStorage(): Storage | null {
  try {
    return typeof window !== "undefined" ? window.localStorage : null;
  } catch {
    setStorageError("UNAVAILABLE", "Browser storage is unavailable.");
    return null;
  }
}

function isPlainObject(value: unknown): value is Record<string, unknown> {
  return value !== null && typeof value === "object" && !Array.isArray(value);
}

function safeTimestamp(value: unknown, fallback: number = Date.now()): number {
  return typeof value === "number" && Number.isFinite(value) && value > 0 ? value : fallback;
}

function sanitizeMessage(message: unknown): Message | null {
  if (!isPlainObject(message) || !VALID_ROLES.has(message.role as string)) return null;
  if (typeof message.content !== "string") return null;

  const status = VALID_STATUSES.has(message.status as string)
    ? (message.status as Message["status"])
    : "success";
  return {
    id:
      typeof message.id === "string" && message.id.length <= 160
        ? message.id
        : generateId(),
    role: message.role as Message["role"],
    content: message.content.slice(0, STORAGE_LIMITS.maxMessageChars),
    timestamp: safeTimestamp(message.timestamp),
    status,
    ...(typeof message.originalQuestion === "string"
      ? { originalQuestion: message.originalQuestion.slice(0, STORAGE_LIMITS.maxMessageChars) }
      : {}),
    ...(typeof message.errorCode === "string"
      ? { errorCode: message.errorCode.slice(0, 80) }
      : {}),
    ...(Array.isArray(message.sources)
      ? { sources: message.sources.map(sanitizeSource).filter((s): s is Source => s !== null).slice(0, 100) }
      : {}),
  };
}

function sanitizeSource(source: unknown): Source | null {
  if (!isPlainObject(source)) return null;
  const rawUrl = typeof source.url === "string" ? source.url.trim().slice(0, 2_000) : "";
  const url = /^(?:https?:|#)/iu.test(rawUrl) ? rawUrl : "";
  return {
    title: typeof source.title === "string" ? source.title.slice(0, 300) : "",
    source: typeof source.source === "string" ? source.source.slice(0, 500) : "",
    department:
      typeof source.department === "string" ? source.department.slice(0, 200) : "",
    page:
      typeof source.page === "number" || typeof source.page === "string"
        ? String(source.page).slice(0, 40)
        : "",
    url,
    id: typeof source.id === "string" ? source.id.slice(0, 160) : "",
  };
}

function sanitizeMessages(messages: unknown): Message[] {
  if (!Array.isArray(messages)) return [];
  return messages
    .map(sanitizeMessage)
    .filter((message): message is Message => message !== null)
    .filter((message) => message.status !== "pending")
    .slice(-STORAGE_LIMITS.maxMessagesPerChat);
}

function sanitizeRecord(id: unknown, record: unknown): ChatRecord | null {
  if (!isPlainObject(record) || typeof id !== "string" || !id) return null;
  const messages = sanitizeMessages(record.messages);
  const firstUser = messages.find((message) => message.role === "user");
  const lastAssistant = [...messages]
    .reverse()
    .find((message) => message.role === "assistant");
  const title =
    typeof record.title === "string" && record.title.trim()
      ? record.title.trim().slice(0, 80)
      : (firstUser?.content || "New Chat").slice(0, 80);

  return {
    id: id.slice(0, 160),
    messages,
    updatedAt: safeTimestamp(record.updatedAt, messages.at(-1)?.timestamp),
    title,
    preview: (
      typeof record.preview === "string"
        ? record.preview
        : lastAssistant?.content || ""
    ).slice(0, 160),
  };
}

function readAll(): Record<string, ChatRecord> {
  const storage = getStorage();
  if (!storage) return {};

  let parsed: unknown;
  try {
    const raw = storage.getItem(STORAGE_KEY);
    if (!raw) return {};
    parsed = JSON.parse(raw);
  } catch {
    setStorageError("CORRUPT", "Saved chat history could not be read and was reset.");
    try {
      storage.removeItem(STORAGE_KEY);
    } catch {
      /* ignore cleanup failure */
    }
    return {};
  }

  // Version 1 is wrapped so future schema changes can migrate explicitly.
  if (isPlainObject(parsed) && parsed.version === STORAGE_VERSION) {
    if (!isPlainObject(parsed.chats)) {
      setStorageError("CORRUPT", "Saved chat history has an invalid schema.");
      return {};
    }
    return Object.fromEntries(
      Object.entries(parsed.chats)
        .map(([id, record]) => [id, sanitizeRecord(id, record)] as const)
        .filter((entry): entry is [string, ChatRecord] => entry[1] !== null)
    );
  }

  // Migrate the original unversioned map lazily on the next write.
  if (isPlainObject(parsed)) {
    return Object.fromEntries(
      Object.entries(parsed)
        .map(([id, record]) => [id, sanitizeRecord(id, record)] as const)
        .filter((entry): entry is [string, ChatRecord] => entry[1] !== null)
    );
  }

  setStorageError("CORRUPT", "Saved chat history has an invalid schema.");
  return {};
}

function boundedChats(chats: Record<string, ChatRecord>): Record<string, ChatRecord> {
  const sorted = Object.values(chats)
    .filter(Boolean)
    .sort((a, b) => b.updatedAt - a.updatedAt)
    .slice(0, STORAGE_LIMITS.maxChats);
  let totalChars = 0;
  const result: Record<string, ChatRecord> = {};

  // Keep the most recent chats and messages under a deterministic total cap.
  for (const chat of sorted) {
    const messages: Message[] = [];
    for (const message of [...chat.messages].reverse()) {
      const chars = message.content.length;
      if (totalChars + chars > STORAGE_LIMITS.maxTotalChars) break;
      messages.unshift(message);
      totalChars += chars;
    }
    result[chat.id] = {
      ...chat,
      messages,
      preview: (
        [...messages].reverse().find((message) => message.role === "assistant")
          ?.content || ""
      ).slice(0, 160),
    };
  }
  return result;
}

function writeAll(chats: Record<string, ChatRecord>): StorageResult {
  const storage = getStorage();
  if (!storage) return { ok: false, error: lastStorageError };

  const bounded = boundedChats(chats);
  try {
    storage.setItem(
      STORAGE_KEY,
      JSON.stringify({ version: STORAGE_VERSION, chats: bounded })
    );
    lastStorageError = null;
    return { ok: true, error: null };
  } catch {
    setStorageError("QUOTA", "Chat history could not be saved because storage is full.");
    return { ok: false, error: lastStorageError };
  }
}

export function generateId(): string {
  return `${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 10)}`;
}

/**
 * Persists a single chat. Reads the full stored map once, patches only this
 * chat's entry, and writes the full map back once — one read + one write per
 * call, not one per chat in memory (callers must only invoke this for chats
 * that actually changed).
 */
export function saveChat(sessionId: string, messages: Message[], metadata: ChatMetadata = {}): StorageResult {
  if (typeof sessionId !== "string" || !sessionId || !Array.isArray(messages)) {
    setStorageError("INVALID", "Chat history was not saved because it was invalid.");
    return { ok: false, error: lastStorageError };
  }

  const all = readAll();
  const cleanMessages = sanitizeMessages(messages);
  const existing = all[sessionId] || ({} as Partial<ChatRecord>);
  const firstUser = cleanMessages.find((message) => message.role === "user");
  const result = writeAll({
    ...all,
    [sessionId]: sanitizeRecord(sessionId, {
      ...existing,
      id: sessionId,
      messages: cleanMessages,
      updatedAt: safeTimestamp(metadata.updatedAt, existing.updatedAt),
      title:
        metadata.title || existing.title || (firstUser?.content || "New Chat").slice(0, 80),
      preview: (
        metadata.preview ||
        [...cleanMessages].reverse().find((message) => message.role === "assistant")?.content ||
        ""
      ).slice(0, 160),
    })!,
  });
  return result;
}

export function loadChat(sessionId: string): Message[] {
  const record = readAll()[sessionId];
  return record ? record.messages : [];
}

export function loadChats(): Record<string, ChatRecord> {
  return readAll();
}

export function deleteChat(sessionId: string): StorageResult {
  const all = readAll();
  if (Object.prototype.hasOwnProperty.call(all, sessionId)) delete all[sessionId];
  return writeAll(all);
}

export function getChatList(): ChatListItem[] {
  return Object.values(readAll())
    .sort((a, b) => b.updatedAt - a.updatedAt)
    .map(({ id, title, updatedAt, preview }) => ({ id, title, updatedAt, preview }));
}

export function clearAllChats(): StorageResult {
  const storage = getStorage();
  if (!storage) return { ok: false, error: lastStorageError };
  try {
    storage.removeItem(STORAGE_KEY);
    lastStorageError = null;
    return { ok: true, error: null };
  } catch {
    setStorageError("CLEAR_FAILED", "Chat history could not be cleared.");
    return { ok: false, error: lastStorageError };
  }
}

export function getStorageStatus(): StorageErrorInfo | null {
  return lastStorageError ? { ...lastStorageError } : null;
}

export function resetStorageStatus(): void {
  lastStorageError = null;
}

export { STORAGE_KEY };
