import { useEffect, useRef } from "react";
import type { Citation, GroundingMetadata } from "../api/chat";

export interface Message {
  id: string;
  author: "assistant" | "user";
  text: string;
  agent?: string;
  intent?: string;
  citations?: Citation[];
  groundingMetadata?: GroundingMetadata | null;
  isError?: boolean;
}

interface MessageAreaProps {
  messages: Message[];
  /** True while a request is in flight — renders a lightweight "Analizando…" indicator at the
   * bottom, kept separate from `messages` so the history itself never contains a synthetic
   * "loading" entry. */
  isAssistantTyping: boolean;
}

// Friendly, Spanish-first labels for internal agent class names — PBI-04-04 requirement 7
// ("normal users must never see... internal [identifiers]"): the raw class name (e.g.
// "ClaimsAgent") is a technical detail; the caller only needs to know which specialist is
// helping them, in their own language.
const AGENT_LABELS: Record<string, string> = {
  ClaimsAgent: "Siniestros",
  BrokerAgent: "Servicios a Corredores",
  CommercialIntakeAgent: "Nuevos Negocios",
  FallbackAgent: "Asistente",
};

function AgentBadge({ agent }: { agent: string }) {
  return <span className="agent-badge">{AGENT_LABELS[agent] ?? "Asistente"}</span>;
}

function CitationCard({ citation }: { citation: Citation }) {
  return (
    <li className="citation-card">
      <span className="citation-card__marker">[{citation.reference.referenceId}]</span>
      <span className="citation-card__title">{citation.title}</span>
      {citation.section && <span className="citation-card__section"> — {citation.section}</span>}
    </li>
  );
}

function GroundingBadge({ grounding }: { grounding: GroundingMetadata }) {
  if (!grounding.isGrounded) {
    return null;
  }
  return (
    <span className="grounding-badge">
      Basado en {grounding.citationCount} fuente{grounding.citationCount === 1 ? "" : "s"}
    </span>
  );
}

export function MessageArea({ messages, isAssistantTyping }: MessageAreaProps) {
  const bottomRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [messages, isAssistantTyping]);

  return (
    <div className="message-area">
      {messages.map((message) => (
        <div
          key={message.id}
          className={`message message--${message.author}${message.isError ? " message--error" : ""}`}
        >
          {message.author === "assistant" && message.agent && !message.isError && (
            <AgentBadge agent={message.agent} />
          )}
          <div className="message__text">{message.text}</div>
          {message.groundingMetadata && <GroundingBadge grounding={message.groundingMetadata} />}
          {message.citations && message.citations.length > 0 && (
            <ul className="citation-list">
              {message.citations.map((citation) => (
                <CitationCard key={citation.reference.referenceId} citation={citation} />
              ))}
            </ul>
          )}
        </div>
      ))}
      {isAssistantTyping && (
        <div className="message message--assistant message--typing" role="status" aria-live="polite">
          <span className="typing-indicator" aria-label="Analizando tu mensaje">
            <span />
            <span />
            <span />
          </span>
          <span className="typing-indicator__label">Analizando…</span>
        </div>
      )}
      <div ref={bottomRef} />
    </div>
  );
}
