import { describe, expect, it, vi, beforeEach } from "vitest";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { AccountInfo, IPublicClientApplication } from "@azure/msal-browser";
import { InteractionStatus } from "@azure/msal-browser";
import * as msalReact from "@azure/msal-react";
import { App } from "./App";
import * as chatApi from "./api/chat";

vi.mock("./api/chat", async () => {
  const actual = await vi.importActual<typeof chatApi>("./api/chat");
  return { ...actual, sendChatMessage: vi.fn() };
});

// PBI-11-01: every pre-existing chat-flow test below now runs "already signed in" — App's
// MSAL sign-in gate and token acquisition are exercised separately (see the "sign-in gate"
// describe block at the bottom of this file).
vi.mock("./auth/getAccessToken", () => ({
  getAccessToken: vi.fn().mockResolvedValue("test-access-token"),
}));

vi.mock("@azure/msal-react", async () => {
  const actual = await vi.importActual<typeof msalReact>("@azure/msal-react");
  return { ...actual, useMsal: vi.fn() };
});

const sendChatMessageMock = vi.mocked(chatApi.sendChatMessage);
const useMsalMock = vi.mocked(msalReact.useMsal);

const fakeAccount: AccountInfo = {
  homeAccountId: "test-home-account-id",
  environment: "login.microsoftonline.com",
  tenantId: "11111111-1111-1111-1111-111111111111",
  username: "test.user@example.com",
  name: "Test User",
  localAccountId: "test-local-account-id",
} as AccountInfo;

const fakeInstance = {
  loginPopup: vi.fn(),
  logoutPopup: vi.fn(),
  acquireTokenSilent: vi.fn(),
  acquireTokenPopup: vi.fn(),
} as unknown as IPublicClientApplication;

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

describe("App (authenticated)", () => {
  beforeEach(() => {
    sendChatMessageMock.mockReset();
    window.localStorage.clear();
    window.sessionStorage.clear();
    useMsalMock.mockReturnValue({
      instance: fakeInstance,
      accounts: [fakeAccount],
      inProgress: InteractionStatus.None,
    } as unknown as ReturnType<typeof msalReact.useMsal>);
  });

  it("sends the first message without a conversationId, then reuses the returned conversationId on the next turn", async () => {
    const user = userEvent.setup();
    sendChatMessageMock
      .mockResolvedValueOnce(claimsResponse("conv-123"))
      .mockResolvedValueOnce({ ...claimsResponse("conv-123"), response: "Thank you." });
    render(<App />);

    await user.type(screen.getByLabelText("Mensaje"), "I want to report an accident.");
    await user.click(screen.getByRole("button", { name: "Enviar" }));

    await waitFor(() => expect(sendChatMessageMock).toHaveBeenCalledTimes(1));
    expect(sendChatMessageMock.mock.calls[0][0]).toMatchObject({
      accessToken: "test-access-token",
      message: "I want to report an accident.",
      conversationId: null,
    });

    await user.type(screen.getByLabelText("Mensaje"), "SYN-POL-0001");
    await user.click(screen.getByRole("button", { name: "Enviar" }));

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

    await user.type(screen.getByLabelText("Mensaje"), "I want to report an accident.");
    await user.click(screen.getByRole("button", { name: "Enviar" }));

    expect(await screen.findByText("Could you provide your policy number?")).toBeInTheDocument();
  });

  it("displays the authenticated account's name in the header", async () => {
    render(<App />);

    expect(await screen.findByText("Test User")).toBeInTheDocument();
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

    await user.type(screen.getByLabelText("Mensaje"), "hello");
    await user.click(screen.getByRole("button", { name: "Enviar" }));

    expect(screen.getByRole("button", { name: "Enviar" })).toBeDisabled();
    expect(screen.getByLabelText("Mensaje")).toBeDisabled();

    resolveRequest(claimsResponse("conv-1"));
    await waitFor(() => expect(screen.getByRole("button", { name: "Enviar" })).not.toBeDisabled());
  });

  it("shows a safe, generic error message (never raw exception details) and offers a working retry", async () => {
    const user = userEvent.setup();
    sendChatMessageMock
      .mockRejectedValueOnce(new chatApi.ChatRequestError(500))
      .mockResolvedValueOnce(claimsResponse("conv-1"));
    render(<App />);

    await user.type(screen.getByLabelText("Mensaje"), "I want to report an accident.");
    await user.click(screen.getByRole("button", { name: "Enviar" }));

    expect(await screen.findByText(/ocurrió un problema/)).toBeInTheDocument();
    expect(screen.queryByText(/500/)).not.toBeInTheDocument();

    const retryButton = await screen.findByRole("button", { name: "Reintentar" });
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

    await user.type(screen.getByLabelText("Mensaje"), "I want to report an accident.");
    await user.click(screen.getByRole("button", { name: "Enviar" }));
    await screen.findByText("Could you provide your policy number?");

    await user.click(screen.getByRole("button", { name: "+ Nueva conversación" }));

    expect(messageArea().queryByText("I want to report an accident.")).not.toBeInTheDocument();
    expect(
      messageArea().queryByText("Could you provide your policy number?"),
    ).not.toBeInTheDocument();

    await user.type(screen.getByLabelText("Mensaje"), "another message");
    await user.click(screen.getByRole("button", { name: "Enviar" }));

    await waitFor(() => expect(sendChatMessageMock).toHaveBeenCalledTimes(2));
    expect(sendChatMessageMock.mock.calls[1][0]).toMatchObject({ conversationId: null });
  });

  it("selecting a sidebar example prompt sends it as a chat message", async () => {
    const user = userEvent.setup();
    sendChatMessageMock.mockResolvedValueOnce(claimsResponse("conv-1"));
    render(<App />);

    await user.click(screen.getByRole("button", { name: /Servicios a corredores/ }));

    await waitFor(() => expect(sendChatMessageMock).toHaveBeenCalledTimes(1));
    expect(sendChatMessageMock.mock.calls[0][0]).toMatchObject({
      message: "Quiero conocer mis comisiones.",
    });
  });

  it("Cerrar sesión calls MSAL logoutPopup", async () => {
    const user = userEvent.setup();
    render(<App />);

    await user.click(await screen.findByRole("button", { name: "Cerrar sesión" }));

    expect(fakeInstance.logoutPopup).toHaveBeenCalledTimes(1);
  });
});

describe("App (sign-in gate)", () => {
  beforeEach(() => {
    sendChatMessageMock.mockReset();
    window.localStorage.clear();
    window.sessionStorage.clear();
  });

  it("shows a sign-in screen, not the chat UI, when no account is authenticated", () => {
    useMsalMock.mockReturnValue({
      instance: fakeInstance,
      accounts: [],
      inProgress: InteractionStatus.None,
    } as unknown as ReturnType<typeof msalReact.useMsal>);

    render(<App />);

    expect(screen.getByRole("button", { name: "Iniciar sesión con Microsoft" })).toBeInTheDocument();
    expect(screen.queryByLabelText("Mensaje")).not.toBeInTheDocument();
  });

  it("clicking the sign-in button calls MSAL loginPopup with this API's own scope", async () => {
    const user = userEvent.setup();
    useMsalMock.mockReturnValue({
      instance: fakeInstance,
      accounts: [],
      inProgress: InteractionStatus.None,
    } as unknown as ReturnType<typeof msalReact.useMsal>);
    render(<App />);

    await user.click(screen.getByRole("button", { name: "Iniciar sesión con Microsoft" }));

    expect(fakeInstance.loginPopup).toHaveBeenCalledTimes(1);
    const request = (fakeInstance.loginPopup as ReturnType<typeof vi.fn>).mock.calls[0][0];
    expect(request.scopes).toEqual(["api://67d95215-5a31-416a-99ab-5fe203fb7c32/access_as_user"]);
  });

  it("never renders the chat UI or calls the chat API while unauthenticated", () => {
    useMsalMock.mockReturnValue({
      instance: fakeInstance,
      accounts: [],
      inProgress: InteractionStatus.None,
    } as unknown as ReturnType<typeof msalReact.useMsal>);

    render(<App />);

    expect(sendChatMessageMock).not.toHaveBeenCalled();
  });
});
