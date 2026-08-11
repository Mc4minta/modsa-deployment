import { Component, type ErrorInfo, type ReactNode } from "react";

interface ErrorBoundaryProps {
  children: ReactNode;
}

interface ErrorBoundaryState {
  hasError: boolean;
}

const TEXT = {
  en: {
    title: "Something went wrong.",
    body: "The app hit an unexpected error. Reloading usually fixes it.",
    reload: "Reload",
  },
  th: {
    title: "เกิดข้อผิดพลาด",
    body: "แอปพบข้อผิดพลาดที่ไม่คาดคิด ลองโหลดหน้าใหม่อีกครั้ง",
    reload: "โหลดใหม่",
  },
};

export default class ErrorBoundary extends Component<ErrorBoundaryProps, ErrorBoundaryState> {
  state: ErrorBoundaryState = { hasError: false };

  static getDerivedStateFromError(): ErrorBoundaryState {
    return { hasError: true };
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error("Unhandled UI error:", error, info.componentStack);
  }

  render() {
    if (!this.state.hasError) return this.props.children;

    const lang = document.documentElement.lang === "th" ? "th" : "en";
    const text = TEXT[lang];

    return (
      <div className="error-boundary" role="alert">
        <h1>{text.title}</h1>
        <p>{text.body}</p>
        <button type="button" onClick={() => window.location.reload()}>
          {text.reload}
        </button>
      </div>
    );
  }
}
