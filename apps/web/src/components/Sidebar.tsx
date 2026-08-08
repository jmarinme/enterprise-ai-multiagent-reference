import { useMemo, useState } from "react";
import type { ConversationSummary } from "../api/conversations";

export interface ExamplePrompt {
  label: string;
  text: string;
}

// Spanish-first demo phrasings (PBI-04-04) — each contains a keyword
// src.supervisor.intent.RuleBasedIntentResolver actually matches for the corresponding agent.
// English routing/example prompts remain fully supported by the platform; this list simply
// reflects the default Spanish-first experience.
const EXAMPLE_PROMPTS: ExamplePrompt[] = [
  { label: "Siniestros", text: "Quiero reportar un accidente." },
  { label: "Servicios a corredores", text: "Quiero conocer mis comisiones." },
  { label: "Nuevos negocios", text: "Necesito una cotización para asegurar mi empresa." },
  { label: "Siniestros + Conocimiento", text: "¿Qué documentos necesito para reportar un siniestro?" },
];

interface SidebarProps {
  conversations: ConversationSummary[];
  isLoadingConversations: boolean;
  activeConversationId: string | null;
  onSelectConversation: (conversationId: string) => void;
  onSelectExample: (text: string) => void;
  onNewConversation: () => void;
  disabled?: boolean;
}

function formatRelativeDate(iso: string): string {
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) {
    return "";
  }
  const now = new Date();
  const sameDay =
    date.getFullYear() === now.getFullYear() &&
    date.getMonth() === now.getMonth() &&
    date.getDate() === now.getDate();
  if (sameDay) {
    return date.toLocaleTimeString("es-MX", { hour: "2-digit", minute: "2-digit" });
  }
  return date.toLocaleDateString("es-MX", { day: "2-digit", month: "short" });
}

export function Sidebar({
  conversations,
  isLoadingConversations,
  activeConversationId,
  onSelectConversation,
  onSelectExample,
  onNewConversation,
  disabled = false,
}: SidebarProps) {
  const [searchTerm, setSearchTerm] = useState("");

  const filteredConversations = useMemo(() => {
    const normalized = searchTerm.trim().toLowerCase();
    if (!normalized) {
      return conversations;
    }
    return conversations.filter((conversation) =>
      conversation.title.toLowerCase().includes(normalized),
    );
  }, [conversations, searchTerm]);

  return (
    <aside className="sidebar">
      <button
        type="button"
        className="sidebar__new-conversation"
        onClick={onNewConversation}
        disabled={disabled}
      >
        + Nueva conversación
      </button>

      <div className="sidebar__search">
        <input
          type="search"
          className="sidebar__search-input"
          placeholder="Buscar conversaciones"
          aria-label="Buscar conversaciones"
          value={searchTerm}
          onChange={(event) => setSearchTerm(event.target.value)}
        />
      </div>

      <div className="sidebar__title">Conversaciones recientes</div>
      {isLoadingConversations && <p className="sidebar__note">Cargando…</p>}
      {!isLoadingConversations && filteredConversations.length === 0 && (
        <p className="sidebar__note">
          {conversations.length === 0
            ? "Aún no tienes conversaciones."
            : "No se encontraron conversaciones."}
        </p>
      )}
      <ul className="sidebar__list sidebar__list--history">
        {filteredConversations.map((conversation) => (
          <li key={conversation.conversationId}>
            <button
              type="button"
              className={`sidebar__history-item${
                conversation.conversationId === activeConversationId
                  ? " sidebar__history-item--active"
                  : ""
              }`}
              onClick={() => onSelectConversation(conversation.conversationId)}
              disabled={disabled}
            >
              <span className="sidebar__history-item-title">{conversation.title}</span>
              <span className="sidebar__history-item-date">
                {formatRelativeDate(conversation.updatedAt)}
              </span>
            </button>
          </li>
        ))}
      </ul>

      <div className="sidebar__title">Prueba estos ejemplos</div>
      <ul className="sidebar__list">
        {EXAMPLE_PROMPTS.map((prompt) => (
          <li key={prompt.text}>
            <button
              type="button"
              className="sidebar__item sidebar__item--button"
              onClick={() => onSelectExample(prompt.text)}
              disabled={disabled}
            >
              <span className="sidebar__item-label">{prompt.label}</span>
              <span className="sidebar__item-text">{prompt.text}</span>
            </button>
          </li>
        ))}
      </ul>
      <p className="sidebar__note">Datos sintéticos únicamente — sin pólizas, siniestros o clientes reales.</p>
    </aside>
  );
}
