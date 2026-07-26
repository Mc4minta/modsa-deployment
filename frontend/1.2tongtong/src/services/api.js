const configuredApiUrl = import.meta.env.VITE_API_URL?.trim();
const API_URL = (
  configuredApiUrl ||
  (import.meta.env.PROD ? window.location.origin : "http://localhost:8000")
).replace(/\/+$/, "");

const parsedTimeout = Number(import.meta.env.VITE_API_TIMEOUT_MS);
const REQUEST_TIMEOUT_MS =
  Number.isFinite(parsedTimeout) && parsedTimeout > 0 ? parsedTimeout : 45_000;

const ALLOWED_CONFIDENCE = new Set(["high", "medium", "low"]);
let currentRequest = null;

export class ApiError extends Error {
  constructor(code, message, status = null) {
    super(message);
    this.name = "ApiError";
    this.code = code;
    this.status = status;
  }
}

function safeSource(source) {
  const candidate = source && typeof source === "object" ? source : {};
  let url;

  if (typeof candidate.url === "string") {
    try {
      const parsed = new URL(candidate.url, window.location.origin);
      if (parsed.protocol === "http:" || parsed.protocol === "https:") {
        url = parsed.href;
      }
    } catch {
      url = undefined;
    }
  }

  return {
    source: typeof candidate.source === "string" ? candidate.source : "",
    title: typeof candidate.title === "string" ? candidate.title : "",
    department:
      typeof candidate.department === "string" ? candidate.department : "",
    page:
      typeof candidate.page === "number" || typeof candidate.page === "string"
        ? candidate.page
        : null,
    url,
  };
}

function normalizeResponse(payload) {
  if (!payload || typeof payload !== "object") {
    throw new ApiError("invalid_response", "The server returned invalid data.");
  }

  const answer = typeof payload.answer === "string" ? payload.answer.trim() : "";
  if (!answer) {
    throw new ApiError("invalid_response", "The server returned an empty answer.");
  }

  return {
    answer,
    sources: Array.isArray(payload.sources)
      ? payload.sources.map(safeSource).filter((source) => source.source || source.title)
      : [],
    confidence: ALLOWED_CONFIDENCE.has(payload.confidence)
      ? payload.confidence
      : "low",
  };
}

export async function askQuestion(question, language = "en") {
  cancelRequest();

  const controller = new AbortController();
  const request = { controller, timedOut: false };
  const timeoutId = window.setTimeout(() => {
    request.timedOut = true;
    controller.abort();
  }, REQUEST_TIMEOUT_MS);
  currentRequest = request;

  try {
    const response = await fetch(`${API_URL}/chat/ask`, {
      method: "POST",
      headers: {
        Accept: "application/json",
        "Accept-Language": language === "th" ? "th" : "en",
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ question }),
      signal: controller.signal,
    });

    if (!response.ok) {
      let detail = "";
      try {
        const body = await response.json();
        detail = typeof body.detail === "string" ? body.detail : "";
      } catch {
        detail = "";
      }

      const code =
        response.status === 429
          ? "rate_limited"
          : response.status >= 500
            ? "server_error"
            : "request_rejected";
      throw new ApiError(code, detail || `Request failed (${response.status}).`, response.status);
    }

    return normalizeResponse(await response.json());
  } catch (error) {
    if (error instanceof ApiError) throw error;
    if (error.name === "AbortError") {
      const code = request.timedOut ? "timeout" : "cancelled";
      throw new ApiError(code, code === "timeout" ? "The request timed out." : "Request cancelled.");
    }
    throw new ApiError("network", "The service could not be reached.");
  } finally {
    window.clearTimeout(timeoutId);
    if (currentRequest === request) currentRequest = null;
  }
}

export function cancelRequest() {
  currentRequest?.controller.abort();
  currentRequest = null;
}

export async function checkHealth() {
  const controller = new AbortController();
  const timeoutId = window.setTimeout(() => controller.abort(), 5_000);

  try {
    const response = await fetch(`${API_URL}/health`, {
      headers: { Accept: "application/json" },
      signal: controller.signal,
    });
    return response.ok;
  } catch {
    return false;
  } finally {
    window.clearTimeout(timeoutId);
  }
}
