export const MAX_QUESTION_LENGTH = 1500;

const SECRET_PATTERNS = [
  /\b(?:password|passwd|pwd)\s*[:=]\s*\S+/iu,
  /\b(?:api[ _-]?key|access[ _-]?token|client[ _-]?secret|secret|token)\s*[:=]\s*\S+/iu,
  /\b(?:sk-[A-Za-z0-9]{20,}|gh[pousr]_[A-Za-z0-9_]{20,}|AIza[0-9A-Za-z_-]{20,}|AKIA[0-9A-Z]{16})\b/u,
  /\beyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\b/u,
  /-----BEGIN [A-Z ]+ PRIVATE KEY-----/u,
  /\bprivate[ _-]?key\s*[:=]\s*\S+/iu,
];

const THAI_SENSITIVE_TERMS =
  /(?:เลขบัตรประชาชน|เลขประจำตัวประชาชน|หมายเลขบัตรประชาชน|บัตรประชาชน|รหัสผ่าน|คีย์\s*API)/iu;

const NATIONAL_ID_PATTERN = /(?:\d[\s-]*){13}/u;

export function normalizeQuestion(value) {
  return typeof value === "string" ? value.trim() : "";
}

export function containsSensitiveInput(value) {
  const question = normalizeQuestion(value);
  if (SECRET_PATTERNS.some((pattern) => pattern.test(question))) return true;
  if (THAI_SENSITIVE_TERMS.test(question)) return true;

  const digits = question.replace(/[\s-]/g, "");
  return NATIONAL_ID_PATTERN.test(question) && /^(?:\d){13}$/.test(digits);
}

export function validateQuestion(value, options = {}) {
  const maxLength = options.maxLength ?? MAX_QUESTION_LENGTH;
  const question = normalizeQuestion(value);

  if (!question) return { valid: false, errorCode: "empty" };

  if (Array.from(question).length > maxLength) {
    return { valid: false, errorCode: "too_long", maxLength };
  }

  if (containsSensitiveInput(question)) {
    return { valid: false, errorCode: "sensitive" };
  }

  return { valid: true, value: question };
}
