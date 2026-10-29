/** Access token of the E2E API (FORJA_E2E_TOKEN to reuse a server started with another one). */
export const E2E_TOKEN = process.env.FORJA_E2E_TOKEN ?? "token-do-e2e";
export const STORAGE_STATE = ".auth/e2e.json";
