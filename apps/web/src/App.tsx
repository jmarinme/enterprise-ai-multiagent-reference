import { useState } from "react";
import { Header } from "./components/Header";
import { Sidebar } from "./components/Sidebar";
import { MessageArea } from "./components/MessageArea";
import type { Message } from "./components/MessageArea";
import { MessageInput } from "./components/MessageInput";
import { ChatRequestError, sendChatMessage } from "./api/chat";
import { getOrCreateUserId } from "./utils/userId";
import "./App.css";

const WELCOME_MESSAGE: Message = {
  id: "welcome",
  author: "assistant",
  text:
    "Welcome to the TMX Agent Platform. Ask about a claim, a broker commission, or a " +
    "commercial insurance quote — a Supervisor Agent reads your message and routes it to " +
    "the right specialist automatically. Try one of the examples on the left, or type your own.",
};

// Never expose a raw backend exception/status text to the user (PBI-04-02 requirement).
const GENERIC_ERROR_TEXT =
  "Sorry, something went wrong reaching the TMX Agent Platform. Please try again.";

let nextMessageId = 1;

function newId(): string {
  return `m-${nextMessageId++}`;
}

export function App() {
  const [messages, setMessages] = useState<Message[]>([WELCOME_MESSAGE]);
  const [conversationId, setConversationId] = useState<string | null>(null);
  const [isSending, setIsSending] = useState(false);
  const [lastFailedMessage, setLastFailedMessage] = useState<string | null>(null);
  const [userId] = useState(getOrCreateUserId);

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
      const assistantMessage: Message = {
        id: newId(),
        author: "assistant",
        text: result.response,
        agent: result.agent,
        intent: result.intent,
        citations: result.citations,
        groundingMetadata: result.groundingMetadata,
        toolCalls: result.toolCalls,
      };
      setMessages((current) => [...current, assistantMessage]);
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
  }

  return (
    <div className="app-shell">
      <Header />
      <div className="app-body">
        <Sidebar
          onSelectExample={(text) => void handleSend(text)}
          onNewConversation={handleNewConversation}
          disabled={isSending}
        />
        <main className="app-main">
          <MessageArea messages={messages} isAssistantTyping={isSending} />
          {lastFailedMessage && !isSending && (
            <div className="retry-banner">
              <span>The last message failed to send.</span>
              <button type="button" className="retry-banner__button" onClick={handleRetry}>
                Retry
              </button>
            </div>
          )}
          <MessageInput onSend={(text) => void handleSend(text)} disabled={isSending} />
        </main>
      </div>
    </div>
  );
}
