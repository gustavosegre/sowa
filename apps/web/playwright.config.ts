import { defineConfig } from "@playwright/test";

const apiPort = process.env.FORJA_API_PORT ?? "8000";
const webPort = process.env.FORJA_WEB_PORT ?? "5173";

export default defineConfig({
  testDir: "./e2e",
  globalSetup: "./e2e/global-setup.ts",
  timeout: 90_000,
  workers: 1,
  use: {
    baseURL: `http://127.0.0.1:${webPort}`,
    trace: "retain-on-failure",
    acceptDownloads: true,
    viewport: { width: 1440, height: 900 },
    locale: "pt-BR",
    storageState: ".auth/e2e.json",
  },
  webServer: [
    {
      command: `uv run --directory ../api uvicorn forja.main:app --port ${apiPort}`,
      url: `http://127.0.0.1:${apiPort}/health`,
      reuseExistingServer: true,
      env: { FORJA_DATA_DIR: "../../.e2e-data" },
    },
    {
      command: `pnpm exec vite --host 127.0.0.1 --port ${webPort}`,
      url: `http://127.0.0.1:${webPort}`,
      reuseExistingServer: true,
      env: { FORJA_API_URL: `http://127.0.0.1:${apiPort}` },
    },
  ],
});
