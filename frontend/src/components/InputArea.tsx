import { useCallback, useEffect, useRef, useState, type KeyboardEvent } from "react";
import { useLanguage } from "../i18n/LanguageContext";
import { MAX_QUESTION_LENGTH, validateQuestion } from "../utils/guards";

interface InputAreaProps {
  onSend: (text: string) => void;
  isLoading: boolean;
  onStop: () => void;
  sessionId: string;
  draft?: string;
  onDraftChange?: (draft: string) => void;
}

export default function InputArea({ onSend, isLoading, onStop, sessionId, draft = "", onDraftChange = () => {} }: InputAreaProps) {
  const { lang, t } = useLanguage();
  const [text, setText] = useState("");
  const [validationError, setValidationError] = useState("");
  const [isRecording, setIsRecording] = useState(false);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const recognitionRef = useRef<SpeechRecognitionLike | null>(null);
  const draftRef = useRef(draft);
  draftRef.current = draft;

  useEffect(() => {
    const textarea = textareaRef.current;
    if (textarea) {
      textarea.style.height = "auto";
      textarea.style.height = `${Math.min(textarea.scrollHeight, 160)}px`;
    }
  }, [text]);

  const stopRecognition = useCallback(() => {
    const recognition = recognitionRef.current;
    if (recognition) {
      recognition.onresult = null;
      recognition.onerror = null;
      recognition.onend = null;
      recognition.stop();
      recognitionRef.current = null;
    }
    setIsRecording(false);
  }, []);

  useEffect(() => {
    stopRecognition();
    setText(draftRef.current);
    setValidationError("");
  }, [sessionId, stopRecognition]);

  useEffect(() => () => stopRecognition(), [stopRecognition]);

  const handleSend = useCallback(() => {
    if (isLoading) return;

    const result = validateQuestion(text);
    if (!result.valid) {
      const messageByCode = {
        empty: t("questionRequired"),
        too_long: t("questionTooLong"),
        sensitive: t("sensitiveInput"),
      };
      setValidationError(messageByCode[result.errorCode] || t("invalidQuestion"));
      return;
    }

    setValidationError("");
    onSend(result.value);
    setText("");
    onDraftChange("");
    if (textareaRef.current) textareaRef.current.style.height = "auto";
  }, [isLoading, onDraftChange, onSend, t, text]);

  const handleKeyDown = (event: KeyboardEvent<HTMLTextAreaElement>) => {
    if (
      event.key === "Enter" &&
      !event.shiftKey &&
      !event.nativeEvent.isComposing &&
      event.keyCode !== 229
    ) {
      event.preventDefault();
      handleSend();
    }
  };

  const toggleVoice = () => {
    if (!("webkitSpeechRecognition" in window || "SpeechRecognition" in window)) {
      setValidationError(t("voiceNotSupported"));
      return;
    }

    if (isRecording) {
      stopRecognition();
      return;
    }

    const SpeechRecognitionCtor = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SpeechRecognitionCtor) {
      setValidationError(t("voiceNotSupported"));
      return;
    }
    const recognition = new SpeechRecognitionCtor();
    recognition.continuous = false;
    recognition.interimResults = false;
    recognition.lang = lang === "th" ? "th-TH" : "en-US";
    recognition.onresult = (event) => {
      const transcript = event.results[0]?.[0]?.transcript || "";
      setText((previous) => {
        const next = Array.from(`${previous}${transcript}`)
          .slice(0, MAX_QUESTION_LENGTH)
          .join("");
        onDraftChange(next);
        return next;
      });
      setValidationError("");
      setIsRecording(false);
      recognitionRef.current = null;
    };
    recognition.onerror = (event) => {
      if (event.error === "not-allowed" || event.error === "permission-denied") {
        setValidationError(t("voicePermissionDenied"));
      } else if (event.error === "no-speech" || event.error === "aborted") {
        // benign — user simply stopped talking or cancelled, no message needed
      } else {
        setValidationError(t("voiceNotSupported"));
      }
      setIsRecording(false);
      recognitionRef.current = null;
    };
    recognition.onend = () => {
      setIsRecording(false);
      recognitionRef.current = null;
    };
    recognitionRef.current = recognition;
    recognition.start();
    setIsRecording(true);
  };

  const characterCount = Array.from(text).length;
  const canSend = characterCount > 0 && characterCount <= MAX_QUESTION_LENGTH && !isLoading;

  return (
    <div className="input-area" id="input-area">
      <div className="input-container">
        <button
          className={`input-action-btn ${isRecording ? "recording" : ""}`}
          onClick={toggleVoice}
          title={isRecording ? t("recording") : t("voiceInput")}
          aria-label={isRecording ? t("recording") : t("voiceInput")}
          id="btn-voice"
          type="button"
        >
          {isRecording ? (
            <div className="recording-indicator" aria-hidden="true">
              <span className="rec-dot" />
            </div>
          ) : (
            <svg width="20" height="20" viewBox="0 0 20 20" fill="none" aria-hidden="true">
              <rect x="7" y="2" width="6" height="10" rx="3" stroke="currentColor" strokeWidth="1.5" />
              <path d="M4 10C4 13.3137 6.68629 16 10 16C13.3137 16 16 13.3137 16 10" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
              <path d="M10 16V19M7 19H13" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
            </svg>
          )}
        </button>

        <textarea
          ref={textareaRef}
          className="chat-textarea"
          placeholder={t("inputPlaceholder")}
          value={text}
          onChange={(event) => {
            const next = Array.from(event.target.value)
              .slice(0, MAX_QUESTION_LENGTH)
              .join("");
            setText(next);
            onDraftChange(next);
            if (validationError) setValidationError("");
          }}
          onKeyDown={handleKeyDown}
          rows={1}
          maxLength={MAX_QUESTION_LENGTH}
          aria-label={t("inputPlaceholder")}
          aria-describedby="input-status"
          id="chat-input"
        />

        <button
          className={isLoading ? "send-btn stop-btn" : "send-btn"}
          onClick={isLoading ? onStop : handleSend}
          disabled={!isLoading && !canSend}
          title={isLoading ? t("stop") : t("send")}
          aria-label={isLoading ? t("stop") : t("send")}
          id={isLoading ? "btn-stop" : "btn-send"}
          type="button"
        >
          {isLoading ? (
            <svg width="16" height="16" viewBox="0 0 16 16" fill="none" aria-hidden="true">
              <rect x="3" y="3" width="10" height="10" rx="2" fill="currentColor" />
            </svg>
          ) : (
            <svg width="18" height="18" viewBox="0 0 18 18" fill="none" aria-hidden="true">
              <path d="M3 9L15 3L9 15L8 10L3 9Z" fill="currentColor" stroke="currentColor" strokeWidth="1" strokeLinejoin="round" />
            </svg>
          )}
        </button>
      </div>
      <div id="input-status" className="input-status" aria-live="polite">
        {validationError || `${characterCount}/${MAX_QUESTION_LENGTH} ${t("charCount")}`}
      </div>
    </div>
  );
}
