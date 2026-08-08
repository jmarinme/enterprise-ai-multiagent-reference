/** Persists the currently-open conversationId across a page refresh or browser reopen
 * (PBI-04-04's history-sidebar requirement) — separate from the synthetic userId (userId.ts),
 * which never changes; this value changes every time a different conversation is opened or a
 * new one is started.
 */

const STORAGE_KEY = "tmx-web-active-conversation-id";

export function getStoredActiveConversationId(): string | null {
  try {
    return window.localStorage.getItem(STORAGE_KEY);
  } catch {
    return null;
  }
}

export function setStoredActiveConversationId(conversationId: string | null): void {
  try {
    if (conversationId) {
      window.localStorage.setItem(STORAGE_KEY, conversationId);
    } else {
      window.localStorage.removeItem(STORAGE_KEY);
    }
  } catch {
    // localStorage unavailable — the active conversation simply won't survive a reload, which
    // is a safe degradation, not a crash.
  }
}
