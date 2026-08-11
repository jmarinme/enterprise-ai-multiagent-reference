import type { AccountInfo } from "@azure/msal-browser";
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
}

export function Header({ account, onSignOut }: HeaderProps) {
  const { connectivity } = useApiStatus();
  const displayName = account.name ?? account.username;

  return (
    <header className="app-header">
      <div className="app-header__title">TMX — Asistente de Seguros AI</div>
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
