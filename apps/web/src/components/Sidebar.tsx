export interface ExamplePrompt {
  label: string;
  text: string;
}

// Real, working demo phrasings (PBI-04-02) — each contains a keyword
// src.supervisor.intent.RuleBasedIntentResolver actually matches, verified against
// tests/unit/api/test_chat.py's own passing end-to-end scenarios. Not new synthetic data —
// these are the platform's existing, already-tested capabilities.
const EXAMPLE_PROMPTS: ExamplePrompt[] = [
  { label: "Claims", text: "I want to report an accident." },
  { label: "Broker Services", text: "I want to check my commissions." },
  { label: "Commercial Intake", text: "I need a commercial insurance quote." },
  { label: "Claims + Knowledge (RAG)", text: "What documents do I need to report a claim?" },
];

interface SidebarProps {
  onSelectExample: (text: string) => void;
  onNewConversation: () => void;
  disabled?: boolean;
}

export function Sidebar({ onSelectExample, onNewConversation, disabled = false }: SidebarProps) {
  return (
    <aside className="sidebar">
      <button
        type="button"
        className="sidebar__new-conversation"
        onClick={onNewConversation}
        disabled={disabled}
      >
        + New conversation
      </button>

      <div className="sidebar__title">Platform capabilities</div>
      <p className="sidebar__note">
        A single Supervisor Agent reads every message and routes it to the right specialist —
        Claims, Broker Services, or Commercial Intake. Try an example:
      </p>
      <ul className="sidebar__list">
        {EXAMPLE_PROMPTS.map((prompt) => (
          <li key={prompt.text}>
            <button
              type="button"
              className="sidebar__item sidebar__item--button"
              onClick={() => onSelectExample(prompt.text)}
              disabled={disabled}
            >
              <span className="sidebar__item-label">{prompt.label}</span>
              <span className="sidebar__item-text">{prompt.text}</span>
            </button>
          </li>
        ))}
      </ul>
      <p className="sidebar__note">Synthetic data only — no real policies, claims, or customers.</p>
    </aside>
  );
}
