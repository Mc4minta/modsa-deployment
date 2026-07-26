export const MAX_QUESTION_LENGTH = 1_500;

const sensitivePatterns = [
  /\b(?:api[_ -]?key|password|passcode|secret)\b/i,
  /(?:รหัสผ่าน|เลขบัตรประชาชน)/u,
  /(?:^|\D)\d{13}(?:\D|$)/,
];

export function validateQuestion(value) {
  const question = typeof value === "string" ? value.trim() : "";

  if (!question) {
    return { ok: false, code: "empty", question: "" };
  }
  if (question.length > MAX_QUESTION_LENGTH) {
    return { ok: false, code: "too_long", question };
  }
  if (sensitivePatterns.some((pattern) => pattern.test(question))) {
    return { ok: false, code: "sensitive", question };
  }

  return { ok: true, code: null, question };
}

export function hasVerifiedSources(sources) {
  return Array.isArray(sources) && sources.length > 0;
}
