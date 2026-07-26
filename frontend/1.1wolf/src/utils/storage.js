const STORAGE_KEY = "modsa-chats";

function readAll() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    return raw ? JSON.parse(raw) : {};
  } catch {
    return {};
  }
}

function writeAll(data) {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(data));
  } catch {
    /* storage full — silently fail */
  }
}

export function generateId() {
  return Date.now().toString(36) + Math.random().toString(36).slice(2, 7);
}

export function saveChat(sessionId, messages) {
  const all = readAll();
  const existing = all[sessionId] || {};

  all[sessionId] = {
    ...existing,
    id: sessionId,
    messages,
    updatedAt: Date.now(),
    title:
      existing.title ||
      (messages.find((m) => m.role === "user")?.content || "New Chat").slice(
        0,
        60
      ),
    preview: (
      messages.filter((m) => m.role === "assistant").pop()?.content || ""
    ).slice(0, 80),
  };

  writeAll(all);
}

export function loadChat(sessionId) {
  const all = readAll();
  return all[sessionId]?.messages || [];
}

export function deleteChat(sessionId) {
  const all = readAll();
  delete all[sessionId];
  writeAll(all);
}

export function getChatList() {
  const all = readAll();
  return Object.values(all)
    .sort((a, b) => (b.updatedAt || 0) - (a.updatedAt || 0))
    .map(({ id, title, updatedAt, preview }) => ({
      id,
      title,
      updatedAt,
      preview,
    }));
}

export function clearAllChats() {
  try {
    localStorage.removeItem(STORAGE_KEY);
  } catch {
    /* ignore */
  }
}
