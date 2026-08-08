import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Sidebar } from "./Sidebar";
import type { ConversationSummary } from "../api/conversations";

const CONVERSATIONS: ConversationSummary[] = [
  {
    conversationId: "conv-1",
    title: "Tuve un choque ayer en la tarde.",
    status: "active",
    currentAgent: "ClaimsAgent",
    createdAt: "2026-08-08T10:00:00Z",
    updatedAt: "2026-08-08T10:05:00Z",
  },
  {
    conversationId: "conv-2",
    title: "Necesito el estado de mis comisiones del segundo trimestre.",
    status: "active",
    currentAgent: "BrokerAgent",
    createdAt: "2026-08-07T10:00:00Z",
    updatedAt: "2026-08-07T10:05:00Z",
  },
];

function renderSidebar(overrides: Partial<Parameters<typeof Sidebar>[0]> = {}) {
  const onSelectConversation = vi.fn();
  const onSelectExample = vi.fn();
  const onNewConversation = vi.fn();
  render(
    <Sidebar
      conversations={CONVERSATIONS}
      isLoadingConversations={false}
      activeConversationId={null}
      onSelectConversation={onSelectConversation}
      onSelectExample={onSelectExample}
      onNewConversation={onNewConversation}
      {...overrides}
    />,
  );
  return { onSelectConversation, onSelectExample, onNewConversation };
}

describe("Sidebar", () => {
  it("renders every conversation's title", () => {
    renderSidebar();

    expect(screen.getByText("Tuve un choque ayer en la tarde.")).toBeInTheDocument();
    expect(screen.getByText("Necesito el estado de mis comisiones del segundo trimestre.")).toBeInTheDocument();
  });

  it("highlights the active conversation", () => {
    renderSidebar({ activeConversationId: "conv-2" });

    const activeItem = screen.getByText("Necesito el estado de mis comisiones del segundo trimestre.").closest("button");
    const inactiveItem = screen.getByText("Tuve un choque ayer en la tarde.").closest("button");
    expect(activeItem).toHaveClass("sidebar__history-item--active");
    expect(inactiveItem).not.toHaveClass("sidebar__history-item--active");
  });

  it("filters the conversation list by the search box", async () => {
    const user = userEvent.setup();
    renderSidebar();

    await user.type(screen.getByLabelText("Buscar conversaciones"), "comisiones");

    expect(screen.queryByText("Tuve un choque ayer en la tarde.")).not.toBeInTheDocument();
    expect(screen.getByText("Necesito el estado de mis comisiones del segundo trimestre.")).toBeInTheDocument();
  });

  it("calls onSelectConversation when a history item is clicked", async () => {
    const user = userEvent.setup();
    const { onSelectConversation } = renderSidebar();

    await user.click(screen.getByText("Tuve un choque ayer en la tarde."));

    expect(onSelectConversation).toHaveBeenCalledWith("conv-1");
  });

  it("shows an empty-state message when there are no conversations yet", () => {
    renderSidebar({ conversations: [] });

    expect(screen.getByText("Aún no tienes conversaciones.")).toBeInTheDocument();
  });

  it("calls onNewConversation when the new-conversation button is clicked", async () => {
    const user = userEvent.setup();
    const { onNewConversation } = renderSidebar();

    await user.click(screen.getByRole("button", { name: "+ Nueva conversación" }));

    expect(onNewConversation).toHaveBeenCalledTimes(1);
  });
});
