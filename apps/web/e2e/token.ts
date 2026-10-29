/** Access token of the E2E API (SOWA_E2E_TOKEN to reuse a server started with another one). */
export const E2E_TOKEN = process.env.SOWA_E2E_TOKEN ?? "token-do-e2e";
export const STORAGE_STATE = ".auth/e2e.json";
