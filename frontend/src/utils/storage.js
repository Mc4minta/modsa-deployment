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
let lastStorageError = null;

function setStorageError(code, message) {
  lastStorageError = { code, message, at: Date.now() };
}

function getStorage() {
  try {
    return typeof window !== "undefined" ? window.localStorage : null;
  } catch {
    setStorageError("UNAVAILABLE", "Browser storage is unavailable.");
    return null;
  }
}

function isPlainObject(value) {
  return value !== null && typeof value === "object" && !Array.isArray(value);
}

function safeTimestamp(value, fallback = Date.now()) {
  return Number.isFinite(value) && value > 0 ? value : fallback;
}

function sanitizeMessage(message) {
  if (!isPlainObject(message) || !VALID_ROLES.has(message.role)) return null;
  if (typeof message.content !== "string") return null;

  const status = VALID_STATUSES.has(message.status) ? message.status : "success";
  return {
    id:
      typeof message.id === "string" && message.id.length <= 160
        ? message.id
        : generateId(),
    role: message.role,
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
      ? { sources: message.sources.map(sanitizeSource).filter(Boolean).slice(0, 100) }
      : {}),
  };
}

function sanitizeSource(source) {
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

function sanitizeMessages(messages) {
  if (!Array.isArray(messages)) return [];
  return messages
    .map(sanitizeMessage)
    .filter(Boolean)
    .filter((message) => message.status !== "pending")
    .slice(-STORAGE_LIMITS.maxMessagesPerChat);
}

function sanitizeRecord(id, record) {
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

function readAll() {
  const storage = getStorage();
  if (!storage) return {};

  let parsed;
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
        .map(([id, record]) => [id, sanitizeRecord(id, record)])
        .filter(([, record]) => record)
    );
  }

  // Migrate the original unversioned map lazily on the next write.
  if (isPlainObject(parsed)) {
    return Object.fromEntries(
      Object.entries(parsed)
        .map(([id, record]) => [id, sanitizeRecord(id, record)])
        .filter(([, record]) => record)
    );
  }

  setStorageError("CORRUPT", "Saved chat history has an invalid schema.");
  return {};
}

function boundedChats(chats) {
  const sorted = Object.values(chats)
    .filter(Boolean)
    .sort((a, b) => b.updatedAt - a.updatedAt)
    .slice(0, STORAGE_LIMITS.maxChats);
  let totalChars = 0;
  const result = {};

  // Keep the most recent chats and messages under a deterministic total cap.
  for (const chat of sorted) {
    const messages = [];
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

function writeAll(chats) {
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

export function generateId() {
  return `${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 10)}`;
}

export function saveChat(sessionId, messages, metadata = {}) {
  if (typeof sessionId !== "string" || !sessionId || !Array.isArray(messages)) {
    setStorageError("INVALID", "Chat history was not saved because it was invalid.");
    return { ok: false, error: lastStorageError };
  }

  const all = readAll();
  const cleanMessages = sanitizeMessages(messages);
  const existing = all[sessionId] || {};
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
    }),
  });
  return result;
}

export function loadChat(sessionId) {
  const record = readAll()[sessionId];
  return record ? record.messages : [];
}

export function loadChats() {
  return readAll();
}

export function deleteChat(sessionId) {
  const all = readAll();
  if (Object.prototype.hasOwnProperty.call(all, sessionId)) delete all[sessionId];
  return writeAll(all);
}

export function getChatList() {
  return Object.values(readAll())
    .sort((a, b) => b.updatedAt - a.updatedAt)
    .map(({ id, title, updatedAt, preview }) => ({ id, title, updatedAt, preview }));
}

export function clearAllChats() {
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

export function getStorageStatus() {
  return lastStorageError ? { ...lastStorageError } : null;
}

export function resetStorageStatus() {
  lastStorageError = null;
}

export { STORAGE_KEY };
