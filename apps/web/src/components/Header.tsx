import { useApiStatus } from "../hooks/useApiStatus";

const CONNECTIVITY_LABEL: Record<string, string> = {
  checking: "Verificando…",
  connected: "Conectado",
  disconnected: "Sin conexión",
};

export function Header() {
  const { connectivity } = useApiStatus();

  return (
    <header className="app-header">
      <div className="app-header__title">TMX — Asistente de Seguros AI</div>
      <div className="app-header__status">
        <span className={`status-badge status-badge--${connectivity}`} role="status">
          {CONNECTIVITY_LABEL[connectivity]}
        </span>
      </div>
    </header>
  );
}
