import { describe, expect, it } from "vitest";
import { MAX_QUESTION_LENGTH, validateQuestion } from "./guards";

describe("validateQuestion", () => {
  it("trims and accepts a normal Student Affairs question", () => {
    expect(validateQuestion("  How do I withdraw from a course?  ")).toEqual({
      ok: true,
      code: null,
      question: "How do I withdraw from a course?",
    });
  });

  it.each([
    ["", "empty"],
    ["my password is secret", "sensitive"],
    ["เลขบัตรประชาชน 1234567890123", "sensitive"],
    ["x".repeat(MAX_QUESTION_LENGTH + 1), "too_long"],
  ])("blocks guarded input", (question, code) => {
    expect(validateQuestion(question)).toMatchObject({ ok: false, code });
  });
});
