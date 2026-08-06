const SAMPLE_HISTORY = ["Sample conversation 1", "Sample conversation 2", "Sample conversation 3"];

/** Placeholder conversation history. Not persisted or interactive in Sprint 0. */
export function Sidebar() {
  return (
    <aside className="sidebar">
      <div className="sidebar__title">Conversation history</div>
      <ul className="sidebar__list">
        {SAMPLE_HISTORY.map((label) => (
          <li key={label} className="sidebar__item" aria-disabled="true">
            {label}
          </li>
        ))}
      </ul>
      <p className="sidebar__note">Illustrative only — history is not implemented in Sprint 0.</p>
    </aside>
  );
}
