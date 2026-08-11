import { describe, expect, it } from "vitest";
import { MAX_QUESTION_LENGTH, validateQuestion } from "../utils/guards";

describe("question guardrails", () => {
  it("trims valid input and rejects empty input", () => {
    expect(validateQuestion("  What is the process?  ")).toMatchObject({
      valid: true,
      value: "What is the process?",
    });
    expect(validateQuestion(" \n\t ")).toMatchObject({ valid: false, errorCode: "empty" });
  });

  it("enforces the Unicode-aware character limit", () => {
    const tooLong = "ก".repeat(MAX_QUESTION_LENGTH + 1);
    expect(validateQuestion(tooLong)).toMatchObject({
      valid: false,
      errorCode: "too_long",
      maxLength: MAX_QUESTION_LENGTH,
    });
  });

  it.each([
    "password: hunter2",
    "api_key=sk-abcdefghijklmnopqrstuvwxyz",
    "1234567890123",
    "เลขบัตรประชาชน 1234567890123",
  ])("rejects sensitive input: %s", (value) => {
    expect(validateQuestion(value)).toMatchObject({ valid: false, errorCode: "sensitive" });
  });
});
