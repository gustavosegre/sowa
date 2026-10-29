import { beforeEach, describe, expect, it, vi } from "vitest";

import { authHeaders, captureTokenFromUrl, clearToken, getToken, setToken, TOKEN_EVENT } from "./token";

describe("access token", () => {
  beforeEach(() => {
    clearToken();
    window.history.replaceState(null, "", "/");
  });

  it("captures #token= from the address and cleans it", () => {
    window.history.replaceState(null, "", "/?project=prj_1#token=abc%2D123");
    expect(captureTokenFromUrl()).toBe("abc-123");
    expect(getToken()).toBe("abc-123");
    expect(window.location.hash).toBe("");
    expect(window.location.search).toBe("?project=prj_1");
    expect(authHeaders()).toEqual({ Authorization: "Bearer abc-123" });
  });

  it("ignores addresses without a token", () => {
    window.history.replaceState(null, "", "/#outra=coisa");
    expect(captureTokenFromUrl()).toBeNull();
    expect(authHeaders()).toEqual({});
  });

  it("announces changes", () => {
    const seen = vi.fn();
    window.addEventListener(TOKEN_EVENT, seen);
    setToken("  com-espacos  ");
    expect(getToken()).toBe("com-espacos");
    clearToken();
    expect(getToken()).toBe("");
    expect(seen).toHaveBeenCalledTimes(2);
    window.removeEventListener(TOKEN_EVENT, seen);
  });
});
