import { useState } from "react";
import { Header } from "./components/Header";
import { Sidebar } from "./components/Sidebar";
import { MessageArea } from "./components/MessageArea";
import type { Message } from "./components/MessageArea";
import { MessageInput } from "./components/MessageInput";
import "./App.css";

const WELCOME_MESSAGE: Message = {
  id: "welcome",
  author: "assistant",
  text: "Welcome to the TMX Enterprise AI Reference Platform. This is a Sprint 0 foundation UI — chat processing and agents are not implemented yet.",
};

const PLACEHOLDER_REPLY_TEXT =
  "This is a placeholder response. Chat processing will be implemented in a later sprint.";

let nextMessageId = 1;

export function App() {
  const [messages, setMessages] = useState<Message[]>([WELCOME_MESSAGE]);

  function handleSend(text: string): void {
    const userMessage: Message = { id: `m-${nextMessageId++}`, author: "user", text };
    const placeholderReply: Message = {
      id: `m-${nextMessageId++}`,
      author: "assistant",
      text: PLACEHOLDER_REPLY_TEXT,
    };
    setMessages((current) => [...current, userMessage, placeholderReply]);
  }

  return (
    <div className="app-shell">
      <Header />
      <div className="app-body">
        <Sidebar />
        <main className="app-main">
          <MessageArea messages={messages} />
          <MessageInput onSend={handleSend} />
        </main>
      </div>
    </div>
  );
}
