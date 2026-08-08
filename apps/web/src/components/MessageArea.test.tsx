import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { MessageArea } from "./MessageArea";
import type { Message } from "./MessageArea";

describe("MessageArea", () => {
  it("renders user and assistant messages", () => {
    const messages: Message[] = [
      { id: "1", author: "user", text: "Hello" },
      { id: "2", author: "assistant", text: "Hi there", agent: "ClaimsAgent" },
    ];

    render(<MessageArea messages={messages} isAssistantTyping={false} />);

    expect(screen.getByText("Hello")).toBeInTheDocument();
    expect(screen.getByText("Hi there")).toBeInTheDocument();
    expect(screen.getByText("Siniestros")).toBeInTheDocument();
  });

  it("renders citations and grounding status when present", () => {
    const messages: Message[] = [
      {
        id: "1",
        author: "assistant",
        text: "Here is what I found.",
        agent: "ClaimsAgent",
        citations: [
          {
            reference: { referenceId: "1", chunkId: "KB-CLAIMS-0002" },
            documentId: "KB-CLAIMS-0002",
            title: "Documents Typically Requested After a Claim Is Reported",
            section: null,
            sourcePath: "configs/knowledge_base/claims_required_documents.md",
            score: 0.5,
          },
        ],
        groundingMetadata: { retrievedCount: 2, citationCount: 1, topK: 2, isGrounded: true },
      },
    ];

    render(<MessageArea messages={messages} isAssistantTyping={false} />);

    expect(
      screen.getByText("Documents Typically Requested After a Claim Is Reported"),
    ).toBeInTheDocument();
    expect(screen.getByText(/Basado en 1 fuente/)).toBeInTheDocument();
  });

  it("does not render a grounding badge when not grounded", () => {
    const messages: Message[] = [
      {
        id: "1",
        author: "assistant",
        text: "Please provide your broker ID.",
        agent: "BrokerAgent",
        groundingMetadata: { retrievedCount: 0, citationCount: 0, topK: 2, isGrounded: false },
      },
    ];

    render(<MessageArea messages={messages} isAssistantTyping={false} />);

    expect(screen.queryByText(/Basado en/)).not.toBeInTheDocument();
  });

  it("renders a typing indicator while a request is in flight", () => {
    render(<MessageArea messages={[]} isAssistantTyping />);

    expect(screen.getByRole("status", { hidden: true })).toBeInTheDocument();
  });

  it("applies the error style and omits the agent badge for an error message", () => {
    const messages: Message[] = [
      { id: "1", author: "assistant", text: "Something went wrong.", isError: true },
    ];

    const { container } = render(<MessageArea messages={messages} isAssistantTyping={false} />);

    expect(container.querySelector(".message--error")).not.toBeNull();
  });
});
