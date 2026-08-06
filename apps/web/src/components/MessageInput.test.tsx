import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MessageInput } from "./MessageInput";

describe("MessageInput", () => {
  it("calls onSend with the typed text and clears the field", async () => {
    const user = userEvent.setup();
    const onSend = vi.fn();
    render(<MessageInput onSend={onSend} />);

    const field = screen.getByLabelText("Message");
    await user.type(field, "Hello there");
    await user.click(screen.getByRole("button", { name: "Send" }));

    expect(onSend).toHaveBeenCalledWith("Hello there");
    expect(field).toHaveValue("");
  });

  it("does not call onSend for blank input", async () => {
    const user = userEvent.setup();
    const onSend = vi.fn();
    render(<MessageInput onSend={onSend} />);

    await user.click(screen.getByRole("button", { name: "Send" }));

    expect(onSend).not.toHaveBeenCalled();
  });
});
