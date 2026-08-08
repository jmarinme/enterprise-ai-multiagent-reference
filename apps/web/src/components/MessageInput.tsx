import { useState } from "react";
import type { FormEvent } from "react";

interface MessageInputProps {
  onSend: (text: string) => void;
  /** True while a request is in flight — disables both the field and the send button
   * (PBI-04-02 requirement: "disabled send button while a request is in flight"). */
  disabled?: boolean;
}

export function MessageInput({ onSend, disabled = false }: MessageInputProps) {
  const [value, setValue] = useState("");

  function handleSubmit(event: FormEvent<HTMLFormElement>): void {
    event.preventDefault();
    if (disabled) {
      return;
    }
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
        placeholder={disabled ? "Waiting for a response…" : "Type a message…"}
        value={value}
        onChange={(event) => setValue(event.target.value)}
        aria-label="Message"
        disabled={disabled}
      />
      <button type="submit" className="message-input__send" disabled={disabled}>
        Send
      </button>
    </form>
  );
}
