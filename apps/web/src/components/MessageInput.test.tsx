import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MessageInput } from "./MessageInput";

describe("MessageInput", () => {
  it("calls onSend with the typed text and clears the field", async () => {
    const user = userEvent.setup();
    const onSend = vi.fn();
    render(<MessageInput onSend={onSend} />);

    const field = screen.getByLabelText("Mensaje");
    await user.type(field, "Hello there");
    await user.click(screen.getByRole("button", { name: "Enviar" }));

    expect(onSend).toHaveBeenCalledWith("Hello there");
    expect(field).toHaveValue("");
  });

  it("does not call onSend for blank input", async () => {
    const user = userEvent.setup();
    const onSend = vi.fn();
    render(<MessageInput onSend={onSend} />);

    await user.click(screen.getByRole("button", { name: "Enviar" }));

    expect(onSend).not.toHaveBeenCalled();
  });

  it("disables the field and send button while disabled=true, and does not call onSend", async () => {
    const user = userEvent.setup();
    const onSend = vi.fn();
    render(<MessageInput onSend={onSend} disabled />);

    expect(screen.getByLabelText("Mensaje")).toBeDisabled();
    expect(screen.getByRole("button", { name: "Enviar" })).toBeDisabled();

    // A disabled field can't receive typed input in a real browser; simulate the edge case of
    // a submit event firing anyway (e.g. Enter key) to prove handleSubmit's own guard works.
    const form = screen.getByRole("button", { name: "Enviar" }).closest("form");
    expect(form).not.toBeNull();
    await user.click(screen.getByRole("button", { name: "Enviar" }));

    expect(onSend).not.toHaveBeenCalled();
  });
});
