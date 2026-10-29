// Access token (the Flowa pattern): read once from the URL fragment (#token=...), kept in
// localStorage, removed from the address bar, sent as a Bearer header.

const KEY = "forja.token";
export const TOKEN_EVENT = "forja:token";

function storage(): Storage | null {
  try {
    return window.localStorage;
  } catch {
    return null;
  }
}

/** Reads `#token=...` from the current URL, stores it and cleans the address bar. */
export function captureTokenFromUrl(location: Location = window.location): string | null {
  const match = /(?:^#|&)token=([^&]+)/.exec(location.hash);
  if (!match?.[1]) return null;
  const token = decodeURIComponent(match[1]);
  setToken(token);
  window.history.replaceState(window.history.state, "", location.pathname + location.search);
  return token;
}

export function getToken(): string {
  try {
    return storage()?.getItem(KEY) ?? "";
  } catch {
    return "";
  }
}

export function setToken(token: string): void {
  try {
    storage()?.setItem(KEY, token.trim());
  } catch {
    // Storage blocked: the token lasts only until the page reloads.
  }
  window.dispatchEvent(new Event(TOKEN_EVENT));
}

export function clearToken(): void {
  try {
    storage()?.removeItem(KEY);
  } catch {
    // ignore
  }
  window.dispatchEvent(new Event(TOKEN_EVENT));
}

export function authHeaders(): Record<string, string> {
  const token = getToken();
  return token ? { Authorization: `Bearer ${token}` } : {};
}
