/** Application runtime configuration derived from Vite environment variables. */

export const apiBaseUrl: string = import.meta.env.VITE_API_URL ?? "http://localhost:8000";
