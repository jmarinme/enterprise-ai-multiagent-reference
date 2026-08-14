import type { AccountInfo } from "@azure/msal-browser";
import { Link, useLocation } from "react-router-dom";
import { useApiStatus } from "../hooks/useApiStatus";

const CONNECTIVITY_LABEL: Record<string, string> = {
  checking: "Verificando…",
  connected: "Conectado",
  disconnected: "Sin conexión",
};

interface HeaderProps {
  /** The authenticated Entra ID account (PBI-11-01) — display only (name/email); never used
   * as an authorization key. */
  account: AccountInfo;
  onSignOut: () => void;
  /** PBI-13-01 §16: shown only when centralized authorization (OBSERVABILITY_ENABLED and,
   * eventually, OBSERVABILITY_ACCESS_MODE=roles + the token's own roles claim) allows it.
   * Header itself never decides the policy — App.tsx passes the already-computed value. */
  showObservabilityNav: boolean;
}

export function Header({ account, onSignOut, showObservabilityNav }: HeaderProps) {
  const { connectivity } = useApiStatus();
  const location = useLocation();
  const displayName = account.name ?? account.username;
  const onObservability = location.pathname.startsWith("/observability");

  return (
    <header className="app-header">
      <div className="app-header__title">TMX — Asistente de Seguros AI</div>
      {showObservabilityNav && (
        <nav className="app-header__nav" aria-label="Navegación principal">
          <Link
            to="/"
            className={`app-header__nav-link${onObservability ? "" : " app-header__nav-link--active"}`}
          >
            Chat
          </Link>
          <Link
            to="/observability"
            className={`app-header__nav-link${onObservability ? " app-header__nav-link--active" : ""}`}
          >
            Observability
          </Link>
        </nav>
      )}
      <div className="app-header__status">
        <span className={`status-badge status-badge--${connectivity}`} role="status">
          {CONNECTIVITY_LABEL[connectivity]}
        </span>
        <span className="app-header__account" title={account.username}>
          {displayName}
        </span>
        <button type="button" className="app-header__sign-out" onClick={onSignOut}>
          Cerrar sesión
        </button>
      </div>
    </header>
  );
}
