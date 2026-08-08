import { useEffect, useState } from "react";
import { Header } from "./components/Header";
import { Sidebar } from "./components/Sidebar";
import { MessageArea } from "./components/MessageArea";
import type { Message } from "./components/MessageArea";
import { MessageInput } from "./components/MessageInput";
import { ChatRequestError, sendChatMessage } from "./api/chat";
import {
  ConversationRequestError,
  getConversation,
  listConversations,
} from "./api/conversations";
import type { ConversationDetail, ConversationSummary } from "./api/conversations";
import { getOrCreateUserId } from "./utils/userId";
import {
  getStoredActiveConversationId,
  setStoredActiveConversationId,
} from "./utils/activeConversation";
import "./App.css";

const WELCOME_MESSAGE: Message = {
  id: "welcome",
  author: "assistant",
  text:
    "Bienvenido al Asistente de Seguros de TMX. Pregúntame sobre un siniestro, una comisión de " +
    "corredor, o una cotización de seguro comercial — leo tu mensaje y te conecto con el " +
    "especialista adecuado automáticamente. Prueba uno de los ejemplos a la izquierda, o " +
    "escribe tu propia pregunta.",
};

// Never expose a raw backend exception/status text to the user (PBI-04-02 requirement).
const GENERIC_ERROR_TEXT =
  "Lo sentimos, ocurrió un problema al conectar con el Asistente de TMX. Por favor intenta de nuevo.";

let nextMessageId = 1;

function newId(): string {
  return `m-${nextMessageId++}`;
}

function mapDetailToMessages(detail: ConversationDetail): Message[] {
  return detail.messages
    .filter((message) => message.role !== "system")
    .map((message, index) => ({
      id: `${detail.conversationId}-${index}`,
      author: message.role === "user" ? "user" : "assistant",
      text: message.content,
    }));
}

export function App() {
  const [messages, setMessages] = useState<Message[]>([WELCOME_MESSAGE]);
  const [conversationId, setConversationId] = useState<string | null>(null);
  const [isSending, setIsSending] = useState(false);
  const [lastFailedMessage, setLastFailedMessage] = useState<string | null>(null);
  const [userId] = useState(getOrCreateUserId);
  const [conversations, setConversations] = useState<ConversationSummary[]>([]);
  const [isLoadingConversations, setIsLoadingConversations] = useState(false);

  async function refreshConversations(): Promise<void> {
    setIsLoadingConversations(true);
    try {
      const result = await listConversations(userId);
      setConversations(result);
    } catch (error) {
      console.error("GET /conversations failed:", error);
    } finally {
      setIsLoadingConversations(false);
    }
  }

  useEffect(() => {
    void refreshConversations();

    const storedId = getStoredActiveConversationId();
    if (storedId) {
      void loadConversation(storedId, { silentOnMissing: true });
    }
    // Only ever run once on mount — userId is stable for the lifetime of this component.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function loadConversation(
    targetConversationId: string,
    options: { silentOnMissing?: boolean } = {},
  ): Promise<void> {
    try {
      const detail = await getConversation(userId, targetConversationId);
      setMessages(mapDetailToMessages(detail));
      setConversationId(detail.conversationId);
      setLastFailedMessage(null);
      setStoredActiveConversationId(detail.conversationId);
    } catch (error) {
      if (error instanceof ConversationRequestError && error.status === 404) {
        // A stored conversation id that no longer resolves (e.g. cleared dev data) should
        // never block the app from starting fresh.
        setStoredActiveConversationId(null);
        if (!options.silentOnMissing) {
          console.error("Conversation not found:", targetConversationId);
        }
        return;
      }
      console.error("GET /conversations/{id} failed:", error);
    }
  }

  async function handleSend(text: string): Promise<void> {
    if (isSending) {
      return;
    }

    const userMessage: Message = { id: newId(), author: "user", text };
    setMessages((current) => [...current, userMessage]);
    setIsSending(true);
    setLastFailedMessage(null);

    try {
      const result = await sendChatMessage({ userId, message: text, conversationId });
      setConversationId(result.conversationId);
      setStoredActiveConversationId(result.conversationId);
      const assistantMessage: Message = {
        id: newId(),
        author: "assistant",
        text: result.response,
        agent: result.agent,
        intent: result.intent,
        citations: result.citations,
        groundingMetadata: result.groundingMetadata,
      };
      setMessages((current) => [...current, assistantMessage]);
      void refreshConversations();
    } catch (error) {
      // ChatRequestError carries only an HTTP status, never a response body — safe to log,
      // never rendered directly. A network failure (no ChatRequestError) is equally generic.
      if (error instanceof ChatRequestError) {
        console.error(`POST /chat failed: HTTP ${error.status}`);
      } else {
        console.error("POST /chat failed:", error);
      }
      setLastFailedMessage(text);
      const errorMessage: Message = {
        id: newId(),
        author: "assistant",
        text: GENERIC_ERROR_TEXT,
        isError: true,
      };
      setMessages((current) => [...current, errorMessage]);
    } finally {
      setIsSending(false);
    }
  }

  function handleRetry(): void {
    if (lastFailedMessage) {
      void handleSend(lastFailedMessage);
    }
  }

  function handleNewConversation(): void {
    setMessages([WELCOME_MESSAGE]);
    setConversationId(null);
    setLastFailedMessage(null);
    setStoredActiveConversationId(null);
  }

  function handleSelectConversation(targetConversationId: string): void {
    if (isSending || targetConversationId === conversationId) {
      return;
    }
    void loadConversation(targetConversationId);
  }

  return (
    <div className="app-shell">
      <Header />
      <div className="app-body">
        <Sidebar
          conversations={conversations}
          isLoadingConversations={isLoadingConversations}
          activeConversationId={conversationId}
          onSelectConversation={handleSelectConversation}
          onSelectExample={(text) => void handleSend(text)}
          onNewConversation={handleNewConversation}
          disabled={isSending}
        />
        <main className="app-main">
          <MessageArea messages={messages} isAssistantTyping={isSending} />
          {lastFailedMessage && !isSending && (
            <div className="retry-banner">
              <span>El último mensaje no se pudo enviar.</span>
              <button type="button" className="retry-banner__button" onClick={handleRetry}>
                Reintentar
              </button>
            </div>
          )}
          <MessageInput onSend={(text) => void handleSend(text)} disabled={isSending} />
        </main>
      </div>
    </div>
  );
}
