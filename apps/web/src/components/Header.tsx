import { useApiStatus } from "../hooks/useApiStatus";

const CONNECTIVITY_LABEL: Record<string, string> = {
  checking: "Checking…",
  connected: "Connected",
  disconnected: "Disconnected",
};

export function Header() {
  const { connectivity, version } = useApiStatus();

  return (
    <header className="app-header">
      <div className="app-header__title">TMX Enterprise AI Reference Platform</div>
      <div className="app-header__status">
        <span className={`status-badge status-badge--${connectivity}`} role="status">
          {CONNECTIVITY_LABEL[connectivity]}
        </span>
        {version && <span className="app-header__version">API v{version}</span>}
      </div>
    </header>
  );
}
