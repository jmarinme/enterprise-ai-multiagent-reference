import { useEffect, useState } from "react";
import { useMsal } from "@azure/msal-react";
import type { AccountInfo, IPublicClientApplication } from "@azure/msal-browser";
import { InteractionStatus } from "@azure/msal-browser";
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
import { getAccessToken } from "./auth/getAccessToken";
import { loginRequest } from "./auth/loginRequest";
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

/** Top-level component: gates the entire application behind Entra ID sign-in (PBI-11-01) — no
 * chat state is created and no API call is ever attempted until a real authenticated account
 * exists. */
export function App() {
  const { instance, accounts, inProgress } = useMsal();
  const account = accounts[0];

  if (!account) {
    return <SignInScreen instance={instance} isSigningIn={inProgress !== InteractionStatus.None} />;
  }

  return <ChatApp instance={instance} account={account} />;
}

function SignInScreen({
  instance,
  isSigningIn,
}: {
  instance: IPublicClientApplication;
  isSigningIn: boolean;
}) {
  return (
    <div className="sign-in-screen">
      <div className="sign-in-screen__card">
        <div className="sign-in-screen__title">TMX — Asistente de Seguros AI</div>
        <p className="sign-in-screen__description">
          Inicia sesión con tu cuenta de Microsoft para usar el asistente. Tus conversaciones
          quedan asociadas a tu identidad autenticada, no a este navegador.
        </p>
        <button
          type="button"
          className="sign-in-screen__button"
          disabled={isSigningIn}
          onClick={() => void instance.loginPopup(loginRequest)}
        >
          {isSigningIn ? "Iniciando sesión…" : "Iniciar sesión con Microsoft"}
        </button>
      </div>
    </div>
  );
}

interface ChatAppProps {
  instance: IPublicClientApplication;
  account: AccountInfo;
}

function ChatApp({ instance, account }: ChatAppProps) {
  const [messages, setMessages] = useState<Message[]>([WELCOME_MESSAGE]);
  const [conversationId, setConversationId] = useState<string | null>(null);
  const [isSending, setIsSending] = useState(false);
  const [lastFailedMessage, setLastFailedMessage] = useState<string | null>(null);
  const [conversations, setConversations] = useState<ConversationSummary[]>([]);
  const [isLoadingConversations, setIsLoadingConversations] = useState(false);

  async function refreshConversations(): Promise<void> {
    setIsLoadingConversations(true);
    try {
      const accessToken = await getAccessToken(instance, account);
      const result = await listConversations(accessToken);
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
    // Only ever run once per signed-in account — account/instance are stable for the lifetime
    // of this component (ChatApp is only mounted once App confirms a real account exists).
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function loadConversation(
    targetConversationId: string,
    options: { silentOnMissing?: boolean } = {},
  ): Promise<void> {
    try {
      const accessToken = await getAccessToken(instance, account);
      const detail = await getConversation(accessToken, targetConversationId);
      setMessages(mapDetailToMessages(detail));
      setConversationId(detail.conversationId);
      setLastFailedMessage(null);
      setStoredActiveConversationId(detail.conversationId);
    } catch (error) {
      if (error instanceof ConversationRequestError && error.status === 404) {
        // A stored conversation id that no longer resolves (e.g. cleared dev data, or it
        // belongs to a different authenticated identity than the one now signed in) should
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
      const accessToken = await getAccessToken(instance, account);
      const result = await sendChatMessage({ accessToken, message: text, conversationId });
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

  function handleSignOut(): void {
    void instance.logoutPopup();
  }

  return (
    <div className="app-shell">
      <Header account={account} onSignOut={handleSignOut} />
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
