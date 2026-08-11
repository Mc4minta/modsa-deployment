import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { LanguageProvider } from "./i18n/LanguageContext";
import ErrorBoundary from "./components/ErrorBoundary";
import App from "./App";
import "./index.css";

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <ErrorBoundary>
      <LanguageProvider>
        <App />
      </LanguageProvider>
    </ErrorBoundary>
  </StrictMode>
);
