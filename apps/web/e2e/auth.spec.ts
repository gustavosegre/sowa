import path from "node:path";

import { expect, test } from "@playwright/test";

import { E2E_USER } from "./global-setup";

test.use({ storageState: { cookies: [], origins: [] } });

test("login, sessão e sair", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByRole("heading", { name: "Entrar na Forja" })).toBeVisible();
  await page.getByLabel("Usuário").fill(E2E_USER.username);
  await page.getByLabel("Senha").fill("senha-errada");
  await page.getByRole("button", { name: "Entrar" }).click();
  await expect(page.getByText("Usuário ou senha incorretos.")).toBeVisible();
  if (process.env.E2E_SHOTS)
    await page.screenshot({ path: path.join(process.env.E2E_SHOTS, "00-login.png") });

  await page.getByLabel("Senha").fill(E2E_USER.password);
  await page.getByRole("button", { name: "Entrar" }).click();
  await expect(page.getByRole("heading", { name: "Forja", exact: true })).toBeVisible();

  await page.getByRole("button", { name: `Usuário: ${E2E_USER.username}` }).click();
  await page.getByRole("menuitem", { name: "Sair" }).click();
  await expect(page.getByRole("heading", { name: "Entrar na Forja" })).toBeVisible();
});
