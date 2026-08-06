import { useState } from "react";
import type { FormEvent } from "react";

interface MessageInputProps {
  onSend: (text: string) => void;
}

export function MessageInput({ onSend }: MessageInputProps) {
  const [value, setValue] = useState("");

  function handleSubmit(event: FormEvent<HTMLFormElement>): void {
    event.preventDefault();
    const trimmed = value.trim();
    if (trimmed.length === 0) {
      return;
    }
    onSend(trimmed);
    setValue("");
  }

  return (
    <form className="message-input" onSubmit={handleSubmit}>
      <input
        type="text"
        className="message-input__field"
        placeholder="Type a message…"
        value={value}
        onChange={(event) => setValue(event.target.value)}
        aria-label="Message"
      />
      <button type="submit" className="message-input__send">
        Send
      </button>
    </form>
  );
}
