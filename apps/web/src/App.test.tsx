import { describe, expect, it, vi, beforeEach } from "vitest";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { App } from "./App";
import * as chatApi from "./api/chat";

vi.mock("./api/chat", async () => {
  const actual = await vi.importActual<typeof chatApi>("./api/chat");
  return { ...actual, sendChatMessage: vi.fn() };
});

const sendChatMessageMock = vi.mocked(chatApi.sendChatMessage);

function claimsResponse(conversationId: string) {
  return {
    conversationId,
    agent: "ClaimsAgent",
    intent: "CLAIMS",
    response: "Could you provide your policy number?",
    citations: [],
    groundingMetadata: null,
    toolCalls: [],
  };
}

describe("App", () => {
  beforeEach(() => {
    sendChatMessageMock.mockReset();
    window.localStorage.clear();
  });

  it("sends the first message without a conversationId, then reuses the returned conversationId on the next turn", async () => {
    const user = userEvent.setup();
    sendChatMessageMock
      .mockResolvedValueOnce(claimsResponse("conv-123"))
      .mockResolvedValueOnce({ ...claimsResponse("conv-123"), response: "Thank you." });
    render(<App />);

    await user.type(screen.getByLabelText("Message"), "I want to report an accident.");
    await user.click(screen.getByRole("button", { name: "Send" }));

    await waitFor(() => expect(sendChatMessageMock).toHaveBeenCalledTimes(1));
    expect(sendChatMessageMock.mock.calls[0][0]).toMatchObject({
      message: "I want to report an accident.",
      conversationId: null,
    });

    await user.type(screen.getByLabelText("Message"), "SYN-POL-0001");
    await user.click(screen.getByRole("button", { name: "Send" }));

    await waitFor(() => expect(sendChatMessageMock).toHaveBeenCalledTimes(2));
    expect(sendChatMessageMock.mock.calls[1][0]).toMatchObject({
      message: "SYN-POL-0001",
      conversationId: "conv-123",
    });
  });

  it("displays the agent's response text after a successful call", async () => {
    const user = userEvent.setup();
    sendChatMessageMock.mockResolvedValueOnce(claimsResponse("conv-1"));
    render(<App />);

    await user.type(screen.getByLabelText("Message"), "I want to report an accident.");
    await user.click(screen.getByRole("button", { name: "Send" }));

    expect(await screen.findByText("Could you provide your policy number?")).toBeInTheDocument();
  });

  it("disables the send button and shows a typing indicator while a request is in flight", async () => {
    const user = userEvent.setup();
    let resolveRequest: (value: ReturnType<typeof claimsResponse>) => void = () => {};
    sendChatMessageMock.mockReturnValueOnce(
      new Promise((resolve) => {
        resolveRequest = resolve;
      }),
    );
    render(<App />);

    await user.type(screen.getByLabelText("Message"), "hello");
    await user.click(screen.getByRole("button", { name: "Send" }));

    expect(screen.getByRole("button", { name: "Send" })).toBeDisabled();
    expect(screen.getByLabelText("Message")).toBeDisabled();

    resolveRequest(claimsResponse("conv-1"));
    await waitFor(() => expect(screen.getByRole("button", { name: "Send" })).not.toBeDisabled());
  });

  it("shows a safe, generic error message (never raw exception details) and offers a working retry", async () => {
    const user = userEvent.setup();
    sendChatMessageMock
      .mockRejectedValueOnce(new chatApi.ChatRequestError(500))
      .mockResolvedValueOnce(claimsResponse("conv-1"));
    render(<App />);

    await user.type(screen.getByLabelText("Message"), "I want to report an accident.");
    await user.click(screen.getByRole("button", { name: "Send" }));

    expect(await screen.findByText(/Sorry, something went wrong/)).toBeInTheDocument();
    expect(screen.queryByText(/500/)).not.toBeInTheDocument();

    const retryButton = await screen.findByRole("button", { name: "Retry" });
    await user.click(retryButton);

    await waitFor(() => expect(sendChatMessageMock).toHaveBeenCalledTimes(2));
    expect(await screen.findByText("Could you provide your policy number?")).toBeInTheDocument();
  });

  it("New conversation clears the message history and conversationId", async () => {
    const user = userEvent.setup();
    sendChatMessageMock
      .mockResolvedValueOnce(claimsResponse("conv-1"))
      .mockResolvedValueOnce(claimsResponse("conv-2"));
    const { container } = render(<App />);
    const messageArea = () => within(container.querySelector(".message-area") as HTMLElement);

    await user.type(screen.getByLabelText("Message"), "I want to report an accident.");
    await user.click(screen.getByRole("button", { name: "Send" }));
    await screen.findByText("Could you provide your policy number?");

    await user.click(screen.getByRole("button", { name: "+ New conversation" }));

    expect(messageArea().queryByText("I want to report an accident.")).not.toBeInTheDocument();
    expect(
      messageArea().queryByText("Could you provide your policy number?"),
    ).not.toBeInTheDocument();

    await user.type(screen.getByLabelText("Message"), "another message");
    await user.click(screen.getByRole("button", { name: "Send" }));

    await waitFor(() => expect(sendChatMessageMock).toHaveBeenCalledTimes(2));
    expect(sendChatMessageMock.mock.calls[1][0]).toMatchObject({ conversationId: null });
  });

  it("selecting a sidebar example prompt sends it as a chat message", async () => {
    const user = userEvent.setup();
    sendChatMessageMock.mockResolvedValueOnce(claimsResponse("conv-1"));
    render(<App />);

    await user.click(screen.getByRole("button", { name: /Broker Services/ }));

    await waitFor(() => expect(sendChatMessageMock).toHaveBeenCalledTimes(1));
    expect(sendChatMessageMock.mock.calls[0][0]).toMatchObject({
      message: "I want to check my commissions.",
    });
  });
});
