import path from "node:path";
import { fileURLToPath } from "node:url";

import { expect, test, type Page } from "@playwright/test";

const here = path.dirname(fileURLToPath(import.meta.url));
const CSV = path.resolve(here, "../../api/tests/fixtures/files/vendas_latin1.csv");
const SHOTS = process.env.E2E_SHOTS;

async function shot(page: Page, name: string) {
  if (SHOTS) await page.screenshot({ path: path.join(SHOTS, `${name}.png`) });
}

const library = (page: Page) => page.getByRole("complementary", { name: "Biblioteca" });
const sidebar = (page: Page) => page.getByRole("complementary", { name: "Configuração do nó" });
const preview = (page: Page) => page.getByRole("region", { name: "Prévia" });

test("template salvo vira sub-fluxo e pode ser expandido", async ({ page }) => {
  const name = `Dobrar ${Date.now()}`;
  await page.goto("/");
  await page.getByRole("button", { name: "Novo projeto" }).first().click();
  await page.getByLabel("Nome do projeto").fill(`E2E templates ${Date.now()}`);
  await page.getByRole("button", { name: "Confirmar" }).click();
  await page.getByRole("button", { name: "Importar arquivo" }).first().click();
  await page.getByTestId("file-input").setInputFiles(CSV);
  await page.getByRole("button", { name: "Avançar" }).click();
  await page.getByRole("button", { name: "Importar", exact: true }).click();
  await page.getByRole("dialog").getByRole("button", { name: "Fechar" }).last().click();

  // One step, saved as a template.
  await library(page).getByRole("button", { name: "Coluna calculada", exact: true }).click();
  await sidebar(page).getByLabel("Nome da coluna").fill("dobro");
  await sidebar(page).getByRole("textbox", { name: "Fórmula" }).click();
  await page.keyboard.type("[quantidade] * 2");
  await page.keyboard.press("Escape");
  await expect(preview(page)).toContainText("9 colunas", { timeout: 15_000 });
  await sidebar(page).getByRole("button", { name: "Salvar como template" }).click();
  const dialog = page.getByRole("dialog");
  await expect(dialog).toContainText("Entradas: vendas_latin1");
  await dialog.getByLabel("Nome do template").fill(name);
  await dialog.getByRole("button", { name: "Salvar" }).click();
  await expect(dialog).toBeHidden();

  // Insert it as a sub-flow after the source.
  const nodes = page.locator('[data-testid^="node-"]');
  await nodes.first().click();
  await library(page).getByRole("tab", { name: "Templates" }).click();
  await library(page)
    .getByRole("button", { name: new RegExp(name) })
    .first()
    .click();
  await expect(nodes).toHaveCount(3);
  await expect(sidebar(page)).toContainText("Etapas");
  await expect(preview(page)).toContainText("4 linhas · 9 colunas", { timeout: 15_000 });
  await shot(page, "15-subflow");

  // Expand back into editable nodes.
  await sidebar(page).getByRole("button", { name: "Expandir em nós editáveis" }).click();
  await expect(nodes).toHaveCount(3);
  await expect(sidebar(page).getByLabel("Nome da coluna")).toHaveValue("dobro");
  await expect(preview(page)).toContainText("4 linhas · 9 colunas", { timeout: 15_000 });
  await shot(page, "16-expanded");
});
