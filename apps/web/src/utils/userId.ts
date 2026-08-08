/** Synthetic, per-browser user identifier for the demo chat UI — no authentication exists yet
 * (explicitly out of scope for PBI-04-02). Persisted in localStorage so a page reload keeps the
 * same identity; a "New conversation" action only resets conversationId/messages, never this.
 */

const STORAGE_KEY = "tmx-web-user-id";

export function getOrCreateUserId(): string {
  try {
    const existing = window.localStorage.getItem(STORAGE_KEY);
    if (existing) {
      return existing;
    }
    const generated = `web-user-${crypto.randomUUID()}`;
    window.localStorage.setItem(STORAGE_KEY, generated);
    return generated;
  } catch {
    // localStorage unavailable (e.g. private browsing edge cases) — fall back to a
    // session-only id rather than failing the whole app.
    return `web-user-${crypto.randomUUID()}`;
  }
}
