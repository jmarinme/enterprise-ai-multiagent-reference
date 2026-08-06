export interface Message {
  id: string;
  author: "assistant" | "user";
  text: string;
}

interface MessageAreaProps {
  messages: Message[];
}

export function MessageArea({ messages }: MessageAreaProps) {
  return (
    <div className="message-area">
      {messages.map((message) => (
        <div key={message.id} className={`message message--${message.author}`}>
          {message.text}
        </div>
      ))}
    </div>
  );
}
