const STORAGE_KEY = "modsa-chats-v2";
const LEGACY_STORAGE_KEY = "modsa-chats";
const RETENTION_MS = 30 * 24 * 60 * 60 * 1_000;
const MAX_CHATS = 30;
const MAX_MESSAGES_PER_CHAT = 80;

function isRecord(value) {
  return Boolean(value) && typeof value === "object" && !Array.isArray(value);
}

function sanitizeMessages(messages) {
  if (!Array.isArray(messages)) return [];

  return messages
    .filter(
      (message) =>
        isRecord(message) &&
        typeof message.content === "string" &&
        (message.role === "user" || message.role === "assistant"),
    )
    .slice(-MAX_MESSAGES_PER_CHAT)
    .map((message) => ({
      id: typeof message.id === "string" ? message.id : generateId(),
      role: message.role,
      content: message.content.slice(0, 20_000),
      sources: Array.isArray(message.sources) ? message.sources.slice(0, 20) : [],
      confidence:
        message.confidence === "high" || message.confidence === "medium"
          ? message.confidence
          : "low",
      status: typeof message.status === "string" ? message.status : "complete",
      errorCode: typeof message.errorCode === "string" ? message.errorCode : undefined,
      originalQuestion:
        typeof message.originalQuestion === "string"
          ? message.originalQuestion.slice(0, 1_500)
          : undefined,
      timestamp: Number.isFinite(message.timestamp) ? message.timestamp : Date.now(),
    }));
}

function readRaw(key) {
  try {
    const parsed = JSON.parse(localStorage.getItem(key) || "{}");
    return isRecord(parsed) ? parsed : {};
  } catch {
    return {};
  }
}

function readAll() {
  const current = readRaw(STORAGE_KEY);
  const legacy = Object.keys(current).length === 0 ? readRaw(LEGACY_STORAGE_KEY) : {};
  const source = Object.keys(current).length > 0 ? current : legacy;
  const cutoff = Date.now() - RETENTION_MS;
  const validEntries = Object.entries(source)
    .filter(([, chat]) => isRecord(chat) && Number(chat.updatedAt) >= cutoff)
    .slice(-MAX_CHATS);

  return Object.fromEntries(validEntries);
}

function writeAll(data) {
  const sortedEntries = Object.entries(data)
    .sort(([, a], [, b]) => Number(b.updatedAt || 0) - Number(a.updatedAt || 0))
    .slice(0, MAX_CHATS);

  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(Object.fromEntries(sortedEntries)));
    localStorage.removeItem(LEGACY_STORAGE_KEY);
    return true;
  } catch {
    return false;
  }
}

export function generateId() {
  if (globalThis.crypto?.randomUUID) return globalThis.crypto.randomUUID();
  return `${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 9)}`;
}

export function saveChat(sessionId, messages) {
  if (!sessionId) return false;

  const safeMessages = sanitizeMessages(messages);
  if (safeMessages.length === 0) return false;

  const all = readAll();
  const existing = isRecord(all[sessionId]) ? all[sessionId] : {};
  const firstQuestion = safeMessages.find((message) => message.role === "user")?.content;
  const lastAnswer = safeMessages
    .filter((message) => message.role === "assistant" && message.status === "complete")
    .at(-1)?.content;

  all[sessionId] = {
    id: sessionId,
    messages: safeMessages,
    updatedAt: Date.now(),
    title: String(existing.title || firstQuestion || "New question").slice(0, 60),
    preview: String(lastAnswer || "").slice(0, 90),
  };

  return writeAll(all);
}

export function loadChat(sessionId) {
  return sanitizeMessages(readAll()[sessionId]?.messages);
}

export function deleteChat(sessionId) {
  const all = readAll();
  delete all[sessionId];
  return writeAll(all);
}

export function getChatList() {
  return Object.values(readAll())
    .filter((chat) => isRecord(chat) && typeof chat.id === "string")
    .sort((a, b) => Number(b.updatedAt || 0) - Number(a.updatedAt || 0))
    .map(({ id, title, updatedAt, preview }) => ({
      id,
      title: String(title || "New question"),
      updatedAt: Number(updatedAt || 0),
      preview: String(preview || ""),
    }));
}

export function clearAllChats() {
  try {
    localStorage.removeItem(STORAGE_KEY);
    localStorage.removeItem(LEGACY_STORAGE_KEY);
    return true;
  } catch {
    return false;
  }
}
