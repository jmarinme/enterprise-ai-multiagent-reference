import { useEffect, useRef } from "react";
import type { Citation, GroundingMetadata, ToolCallResult } from "../api/chat";

export interface Message {
  id: string;
  author: "assistant" | "user";
  text: string;
  agent?: string;
  intent?: string;
  citations?: Citation[];
  groundingMetadata?: GroundingMetadata | null;
  toolCalls?: ToolCallResult[];
  isError?: boolean;
}

interface MessageAreaProps {
  messages: Message[];
  /** True while a request is in flight — renders a lightweight typing indicator at the
   * bottom, kept separate from `messages` so the history itself never contains a synthetic
   * "loading" entry. */
  isAssistantTyping: boolean;
}

function AgentBadge({ agent }: { agent: string }) {
  return <span className="agent-badge">{agent}</span>;
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
      Grounded — {grounding.citationCount} source{grounding.citationCount === 1 ? "" : "s"}
    </span>
  );
}

function ToolCallBadge({ toolCalls }: { toolCalls: ToolCallResult[] }) {
  if (toolCalls.length === 0) {
    return null;
  }
  return (
    <ul className="tool-call-list">
      {toolCalls.map((call) => (
        <li key={call.callId} className={`tool-call-badge tool-call-badge--${call.success ? "ok" : "failed"}`}>
          🔧 {call.toolName} {call.success ? "succeeded" : "failed"}
        </li>
      ))}
    </ul>
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
          {message.toolCalls && <ToolCallBadge toolCalls={message.toolCalls} />}
        </div>
      ))}
      {isAssistantTyping && (
        <div className="message message--assistant message--typing" role="status" aria-live="polite">
          <span className="typing-indicator" aria-label="TMX Agent Platform is responding">
            <span />
            <span />
            <span />
          </span>
        </div>
      )}
      <div ref={bottomRef} />
    </div>
  );
}
