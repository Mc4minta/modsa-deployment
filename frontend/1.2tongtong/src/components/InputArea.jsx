import { useEffect, useRef, useState } from "react";
import { useLanguage } from "../i18n/useLanguage";
import { MAX_QUESTION_LENGTH, validateQuestion } from "../utils/guards";
import { Icon } from "./Icon";

const GUARD_MESSAGES = {
  empty: "guardEmpty",
  too_long: "guardTooLong",
  sensitive: "guardSensitive",
};

export function InputArea({ onSend, isLoading, onStop }) {
  const { lang, t } = useLanguage();
  const [text, setText] = useState("");
  const [validationCode, setValidationCode] = useState(null);
  const [isRecording, setIsRecording] = useState(false);
  const textareaRef = useRef(null);
  const recognitionRef = useRef(null);

  useEffect(() => {
    const textarea = textareaRef.current;
    if (!textarea) return;
    textarea.style.height = "auto";
    textarea.style.height = `${Math.min(textarea.scrollHeight, 176)}px`;
  }, [text]);

  useEffect(
    () => () => {
      recognitionRef.current?.stop();
    },
    [],
  );

  const handleSend = () => {
    if (isLoading) return;
    const result = validateQuestion(text);
    if (!result.ok) {
      setValidationCode(result.code);
      textareaRef.current?.focus();
      return;
    }

    setValidationCode(null);
    onSend(result.question);
    setText("");
  };

  const handleKeyDown = (event) => {
    if (event.key === "Enter" && !event.shiftKey && !event.nativeEvent.isComposing) {
      event.preventDefault();
      handleSend();
    }
  };

  const toggleVoice = () => {
    const SpeechRecognition =
      window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SpeechRecognition) return;

    if (isRecording) {
      recognitionRef.current?.stop();
      return;
    }

    const recognition = new SpeechRecognition();
    recognition.continuous = false;
    recognition.interimResults = false;
    recognition.lang = lang === "th" ? "th-TH" : "en-US";
    recognition.onresult = (event) => {
      const transcript = event.results[0]?.[0]?.transcript || "";
      setText((current) => `${current}${current ? " " : ""}${transcript}`);
    };
    recognition.onerror = () => setIsRecording(false);
    recognition.onend = () => setIsRecording(false);
    recognitionRef.current = recognition;
    recognition.start();
    setIsRecording(true);
  };

  const remaining = MAX_QUESTION_LENGTH - text.length;
  const validationMessage = validationCode
    ? t(GUARD_MESSAGES[validationCode])
    : "";
  const voiceSupported =
    "SpeechRecognition" in window || "webkitSpeechRecognition" in window;

  return (
    <footer className="input-area">
      <div className="composer">
        <div className="composer-tools">
          {voiceSupported && (
            <button
              className={`icon-button ${isRecording ? "recording" : ""}`}
              onClick={toggleVoice}
              title={isRecording ? t("stop") : t("voiceInput")}
              type="button"
              aria-pressed={isRecording}
            >
              <Icon name={isRecording ? "stop" : "mic"} size={19} />
              <span className="sr-only">{isRecording ? t("stop") : t("voiceInput")}</span>
            </button>
          )}
        </div>

        <label className="sr-only" htmlFor="chat-input">
          {t("inputLabel")}
        </label>
        <textarea
          ref={textareaRef}
          id="chat-input"
          className="chat-textarea"
          placeholder={t("inputPlaceholder")}
          value={text}
          onChange={(event) => {
            setText(event.target.value);
            if (validationCode) setValidationCode(null);
          }}
          onKeyDown={handleKeyDown}
          rows={1}
          maxLength={MAX_QUESTION_LENGTH + 1}
          aria-describedby="composer-help composer-validation"
          aria-invalid={Boolean(validationCode)}
        />

        <div className="composer-actions">
          {isLoading ? (
            <button
              className="send-button stop-button"
              onClick={onStop}
              type="button"
              aria-label={t("stop")}
              title={t("stop")}
            >
              <Icon name="stop" size={17} />
            </button>
          ) : (
            <button
              className="send-button"
              onClick={handleSend}
              disabled={!text.trim()}
              type="button"
              aria-label={t("send")}
              title={t("send")}
            >
              <Icon name="arrowUp" size={18} />
            </button>
          )}
        </div>
      </div>

      <div className="composer-meta">
        <span id="composer-help">{t("privacyNote")}</span>
        <span
          className={`character-count ${remaining < 200 ? "visible" : ""} ${
            remaining < 100 ? "warning" : ""
          }`}
        >
          {Math.max(remaining, 0)} {t("characterLimit")}
        </span>
      </div>
      <p id="composer-validation" className="validation-message" role="alert">
        {validationMessage}
      </p>
    </footer>
  );
}
