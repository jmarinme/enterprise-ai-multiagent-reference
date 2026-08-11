import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { MsalProvider } from "@azure/msal-react";
import { App } from "./App";
import { msalInstance } from "./auth/msalInstance";
import "./index.css";

const rootElement = document.getElementById("root");
if (!rootElement) {
  throw new Error("Root element #root was not found in index.html");
}

// MSAL v3+ requires initialize() to resolve before the PublicClientApplication instance is
// used anywhere (including by MsalProvider) — PBI-11-01.
void msalInstance.initialize().then(() => {
  createRoot(rootElement).render(
    <StrictMode>
      <MsalProvider instance={msalInstance}>
        <App />
      </MsalProvider>
    </StrictMode>,
  );
});
