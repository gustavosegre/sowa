import { mkdirSync, writeFileSync } from "node:fs";
import { dirname } from "node:path";

import type { FullConfig } from "@playwright/test";

import { E2E_TOKEN, STORAGE_STATE } from "./token";

/** Stores the E2E token in the browser's localStorage, as opening the #token= address would. */
export default function globalSetup(config: FullConfig) {
  const baseURL = config.projects[0]?.use.baseURL;
  if (!baseURL) throw new Error("baseURL missing in playwright.config.ts");
  mkdirSync(dirname(STORAGE_STATE), { recursive: true });
  const state = {
    cookies: [],
    origins: [{ origin: new URL(baseURL).origin, localStorage: [{ name: "sowa.token", value: E2E_TOKEN }] }],
  };
  writeFileSync(STORAGE_STATE, JSON.stringify(state));
}
