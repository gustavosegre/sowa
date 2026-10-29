import path from "node:path";

import { expect, test } from "@playwright/test";

import { E2E_TOKEN } from "./token";

test.use({ storageState: { cookies: [], origins: [] } });

test("token de acesso: tela, endereço com #token= e sair", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByRole("heading", { name: "Entrar na Forja" })).toBeVisible();
  await page.getByLabel("Token de acesso").fill("token-errado");
  await page.getByRole("button", { name: "Entrar" }).click();
  await expect(page.getByText("Token incorreto.")).toBeVisible();
  if (process.env.E2E_SHOTS)
    await page.screenshot({ path: path.join(process.env.E2E_SHOTS, "00-login.png") });

  await page.getByLabel("Token de acesso").fill(E2E_TOKEN);
  await page.getByRole("button", { name: "Entrar" }).click();
  await expect(page.getByRole("heading", { name: "Forja", exact: true })).toBeVisible();

  await page.getByRole("button", { name: "Sair" }).click();
  await expect(page.getByRole("heading", { name: "Entrar na Forja" })).toBeVisible();

  // The address printed by the API logs in and the token leaves the address bar.
  await page.goto(`/#token=${E2E_TOKEN}`);
  await expect(page.getByRole("heading", { name: "Forja", exact: true })).toBeVisible();
  expect(new URL(page.url()).hash).toBe("");
});

test("workspaces agrupam os projetos", async ({ browser }) => {
  const page = await browser.newPage();
  await page.goto(`/#token=${E2E_TOKEN}`);
  const ws = `Equipe ${Date.now()}`;
  await page.getByRole("button", { name: "Novo projeto" }).first().click();
  await page.getByLabel("Nome do projeto").fill("Projeto do workspace");
  await page.getByRole("dialog").getByLabel("Workspace").fill(ws);
  await page.getByRole("button", { name: "Confirmar" }).click();
  await expect(page.getByTestId("save-status")).toBeVisible({ timeout: 15_000 });
  await page.getByRole("button", { name: "Projetos" }).click();

  const section = page.getByRole("region", { name: ws });
  await expect(section.getByText("Projeto do workspace")).toBeVisible();
  await section.getByRole("button", { name: ws }).click();
  await expect(section.getByText("Projeto do workspace")).toBeHidden();
  await page.close();
});
