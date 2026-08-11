/**
 * API client for the backend chat contract.
 *
 * The caller owns request identity and cancellation. This module deliberately
 * does not keep a module-global AbortController, so one request cannot clear
 * or abort another request by accident.
 */

const configuredApiUrl = (import.meta.env.VITE_API_URL || "").replace(/\/+$/, "");
const API_URL = configuredApiUrl || (import.meta.env.DEV ? "http://localhost:8000" : "");
const DEFAULT_TIMEOUT_MS = 45_000;
const MAX_ANSWER_LENGTH = 100_000;

export class ApiError extends Error {
  constructor(message, { code = "UNKNOWN", status = null, details = null, cause = null } = {}) {
    super(message);
    this.name = "ApiError";
    this.code = code;
    this.status = status;
    this.details = details;
    this.cause = cause;
  }
}

function getErrorDetail(body) {
  if (!body) return "";
  if (typeof body === "string") return body.slice(0, 500);
  if (typeof body.detail === "string") return body.detail.slice(0, 500);
  if (Array.isArray(body.detail)) return "Validation failed";
  if (typeof body.message === "string") return body.message.slice(0, 500);
  return "";
}

function errorForStatus(status, body) {
  const detail = getErrorDetail(body);
  if (status === 400 || status === 422) {
    return new ApiError(detail || "The request was not valid.", {
      code: "VALIDATION",
      status,
      details: body,
    });
  }
  if (status === 401 || status === 403) {
    return new ApiError(detail || "The request is not authorized.", {
      code: "AUTH",
      status,
      details: body,
    });
  }
  if (status === 429) {
    return new ApiError(detail || "Too many requests. Please try again later.", {
      code: "RATE_LIMIT",
      status,
      details: body,
    });
  }
  return new ApiError(detail || `The server returned ${status}.`, {
    code: status >= 500 ? "SERVER" : "HTTP",
    status,
    details: body,
  });
}

function isPlainObject(value) {
  return value !== null && typeof value === "object" && !Array.isArray(value);
}

export function isSafeUrl(value) {
  if (typeof value !== "string" || !value.trim()) return false;
  try {
    const origin = typeof window !== "undefined" ? window.location.origin : "http://localhost";
    const url = new URL(value, origin);
    return url.protocol === "http:" || url.protocol === "https:";
  } catch {
    return false;
  }
}

export function normalizeSource(source, index = 0) {
  if (!isPlainObject(source)) return null;

  const normalized = {
    title: typeof source.title === "string" ? source.title.slice(0, 300) : "",
    source: typeof source.source === "string" ? source.source.slice(0, 500) : "",
    department:
      typeof source.department === "string" ? source.department.slice(0, 200) : "",
    page: typeof source.page === "number" || typeof source.page === "string" ? source.page : "",
    url: isSafeUrl(source.url) ? source.url : "",
    id: typeof source.id === "string" ? source.id.slice(0, 160) : `source-${index + 1}`,
  };

  return normalized.title || normalized.source || normalized.url || normalized.department
    ? normalized
    : null;
}

export function normalizeChatResponse(data) {
  if (!isPlainObject(data) || typeof data.answer !== "string") {
    throw new ApiError("The server returned an invalid answer.", {
      code: "MALFORMED",
      details: data,
    });
  }

  if (data.answer.length > MAX_ANSWER_LENGTH) {
    throw new ApiError("The server returned an oversized answer.", {
      code: "MALFORMED",
      details: { length: data.answer.length },
    });
  }

  if (data.sources !== undefined && !Array.isArray(data.sources)) {
    throw new ApiError("The server returned invalid source data.", {
      code: "MALFORMED",
      details: data,
    });
  }

  return {
    answer: data.answer,
    sources: (data.sources || []).slice(0, 100).map(normalizeSource).filter(Boolean),
  };
}

function composeAbortSignal(signal, timeoutMs) {
  const controller = new AbortController();
  let timedOut = false;
  let timeoutId = null;

  const abortFromCaller = () => controller.abort(signal?.reason);
  if (signal) {
    if (signal.aborted) abortFromCaller();
    else signal.addEventListener("abort", abortFromCaller, { once: true });
  }

  if (timeoutMs > 0) {
    timeoutId = setTimeout(() => {
      timedOut = true;
      controller.abort("timeout");
    }, timeoutMs);
  }

  return {
    signal: controller.signal,
    wasTimedOut: () => timedOut,
    cleanup: () => {
      if (timeoutId) clearTimeout(timeoutId);
      signal?.removeEventListener("abort", abortFromCaller);
    },
  };
}

export async function askQuestion(question, { signal, timeoutMs = DEFAULT_TIMEOUT_MS } = {}) {
  if (typeof question !== "string" || !question.trim()) {
    throw new ApiError("Question cannot be empty.", { code: "VALIDATION", status: 422 });
  }

  const composed = composeAbortSignal(signal, timeoutMs);
  try {
    let response;
    try {
      response = await fetch(`${API_URL}/chat/ask`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question: question.trim() }),
        signal: composed.signal,
      });
    } catch (error) {
      if (composed.wasTimedOut()) {
        throw new ApiError("The request timed out.", { code: "TIMEOUT", cause: error });
      }
      if (composed.signal.aborted) {
        throw new ApiError("The request was cancelled.", { code: "ABORT", cause: error });
      }
      throw new ApiError("Unable to reach the server.", { code: "NETWORK", cause: error });
    }

    let body = null;
    const contentType = response.headers.get("content-type") || "";
    if (contentType.includes("application/json")) {
      try {
        body = await response.json();
      } catch (error) {
        if (!response.ok) body = null;
        else {
          throw new ApiError("The server returned invalid JSON.", {
            code: "MALFORMED",
            status: response.status,
            cause: error,
          });
        }
      }
    } else {
      const text = await response.text();
      body = text ? { detail: text } : null;
    }

    if (!response.ok) throw errorForStatus(response.status, body);
    return normalizeChatResponse(body);
  } finally {
    composed.cleanup();
  }
}

/** Backward-compatible no-op. Cancellation is now owned by the chat hook. */
export function cancelRequest() {
  return false;
}

export async function checkHealth({ signal, timeoutMs = 10_000 } = {}) {
  const composed = composeAbortSignal(signal, timeoutMs);
  try {
    const response = await fetch(`${API_URL}/health`, { signal: composed.signal });
    return response.ok;
  } catch {
    return false;
  } finally {
    composed.cleanup();
  }
}

export { API_URL, DEFAULT_TIMEOUT_MS };
