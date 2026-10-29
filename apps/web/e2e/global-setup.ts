import { request, type FullConfig } from "@playwright/test";

export const E2E_USER = { username: "e2e", password: "e2e-senha-forte" };
export const STORAGE_STATE = ".auth/e2e.json";

/** Logs the E2E user in (creating it on a fresh data dir) and saves the session cookie. */
export default async function globalSetup(config: FullConfig) {
  const baseURL = config.projects[0]?.use.baseURL;
  const ctx = await request.newContext({ baseURL });
  const status = (await (await ctx.get("/api/auth/status")).json()) as { setup_required: boolean };
  const res = await ctx.post(status.setup_required ? "/api/auth/setup" : "/api/auth/login", {
    data: E2E_USER,
  });
  if (!res.ok()) throw new Error(`E2E login failed: ${res.status()} ${await res.text()}`);
  await ctx.storageState({ path: STORAGE_STATE });
  await ctx.dispose();
}
