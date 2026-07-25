import { useState, useRef, useEffect } from "react";
import { useLanguage } from "../i18n/LanguageContext";

export default function InputArea({ onSend, isLoading, onStop }) {
  const { t } = useLanguage();
  const [text, setText] = useState("");
  const [files, setFiles] = useState([]);
  const [isRecording, setIsRecording] = useState(false);
  const textareaRef = useRef(null);
  const fileInputRef = useRef(null);
  const recognitionRef = useRef(null);

  // Auto-resize textarea
  useEffect(() => {
    const ta = textareaRef.current;
    if (ta) {
      ta.style.height = "auto";
      ta.style.height = Math.min(ta.scrollHeight, 160) + "px";
    }
  }, [text]);

  const handleSend = () => {
    const trimmed = text.trim();
    if (!trimmed && files.length === 0) return;
    if (isLoading) return;

    onSend(trimmed, files);
    setText("");
    setFiles([]);

    // Reset textarea height
    if (textareaRef.current) {
      textareaRef.current.style.height = "auto";
    }
  };

  const handleKeyDown = (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const handleFileChange = (e) => {
    const newFiles = Array.from(e.target.files);
    setFiles((prev) => [...prev, ...newFiles].slice(0, 5));
    e.target.value = "";
  };

  const removeFile = (index) => {
    setFiles((prev) => prev.filter((_, i) => i !== index));
  };

  const toggleVoice = () => {
    if (!("webkitSpeechRecognition" in window || "SpeechRecognition" in window)) {
      return;
    }

    if (isRecording) {
      recognitionRef.current?.stop();
      setIsRecording(false);
      return;
    }

    const SpeechRecognition =
      window.SpeechRecognition || window.webkitSpeechRecognition;
    const recognition = new SpeechRecognition();
    recognition.continuous = false;
    recognition.interimResults = false;
    recognition.lang = "th-TH";

    recognition.onresult = (event) => {
      const transcript = event.results[0]?.[0]?.transcript || "";
      setText((prev) => prev + transcript);
      setIsRecording(false);
    };

    recognition.onerror = () => setIsRecording(false);
    recognition.onend = () => setIsRecording(false);

    recognitionRef.current = recognition;
    recognition.start();
    setIsRecording(true);
  };

  const canSend = (text.trim().length > 0 || files.length > 0) && !isLoading;

  return (
    <div className="input-area" id="input-area">
      {/* File preview strip */}
      {files.length > 0 && (
        <div className="file-preview-strip" id="file-preview-strip">
          {files.map((file, i) => (
            <div className="file-preview-item" key={i}>
              <span className="file-preview-icon">
                {file.type.startsWith("image/") ? "🖼️" : "📄"}
              </span>
              <span className="file-preview-name">{file.name}</span>
              <button
                className="file-remove-btn"
                onClick={() => removeFile(i)}
                title={t("removeFile")}
              >
                ×
              </button>
            </div>
          ))}
        </div>
      )}

      <div className="input-container">
        {/* File attach button */}
        <button
          className="input-action-btn"
          onClick={() => fileInputRef.current?.click()}
          title={t("attachFile")}
          id="btn-attach"
        >
          <svg width="20" height="20" viewBox="0 0 20 20" fill="none">
            <path
              d="M14.5 10.5L9 16C7.34315 17.6569 4.65685 17.6569 3 16V16C1.34315 14.3431 1.34315 11.6569 3 10L10.5 2.5C11.6046 1.39543 13.3954 1.39543 14.5 2.5V2.5C15.6046 3.60457 15.6046 5.39543 14.5 6.5L7.5 13.5C6.94772 14.0523 6.05228 14.0523 5.5 13.5V13.5C4.94772 12.9477 4.94772 12.0523 5.5 11.5L11.5 5.5"
              stroke="currentColor"
              strokeWidth="1.5"
              strokeLinecap="round"
            />
          </svg>
        </button>
        <input
          type="file"
          ref={fileInputRef}
          onChange={handleFileChange}
          accept="image/*,.pdf"
          multiple
          hidden
        />

        {/* Voice button */}
        <button
          className={`input-action-btn ${isRecording ? "recording" : ""}`}
          onClick={toggleVoice}
          title={isRecording ? t("recording") : t("voiceInput")}
          id="btn-voice"
        >
          {isRecording ? (
            <div className="recording-indicator">
              <span className="rec-dot"></span>
            </div>
          ) : (
            <svg width="20" height="20" viewBox="0 0 20 20" fill="none">
              <rect
                x="7"
                y="2"
                width="6"
                height="10"
                rx="3"
                stroke="currentColor"
                strokeWidth="1.5"
              />
              <path
                d="M4 10C4 13.3137 6.68629 16 10 16C13.3137 16 16 13.3137 16 10"
                stroke="currentColor"
                strokeWidth="1.5"
                strokeLinecap="round"
              />
              <path
                d="M10 16V19M7 19H13"
                stroke="currentColor"
                strokeWidth="1.5"
                strokeLinecap="round"
              />
            </svg>
          )}
        </button>

        {/* Textarea */}
        <textarea
          ref={textareaRef}
          className="chat-textarea"
          placeholder={t("inputPlaceholder")}
          value={text}
          onChange={(e) => setText(e.target.value)}
          onKeyDown={handleKeyDown}
          rows={1}
          id="chat-input"
        />

        {/* Send / Stop button */}
        {isLoading ? (
          <button
            className="send-btn stop-btn"
            onClick={onStop}
            title={t("stop")}
            id="btn-stop"
          >
            <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
              <rect x="3" y="3" width="10" height="10" rx="2" fill="currentColor" />
            </svg>
          </button>
        ) : (
          <button
            className="send-btn"
            onClick={handleSend}
            disabled={!canSend}
            title={t("send")}
            id="btn-send"
          >
            <svg width="18" height="18" viewBox="0 0 18 18" fill="none">
              <path
                d="M3 9L15 3L9 15L8 10L3 9Z"
                fill="currentColor"
                stroke="currentColor"
                strokeWidth="1"
                strokeLinejoin="round"
              />
            </svg>
          </button>
        )}
      </div>
    </div>
  );
}
