import path from "node:path";
import { fileURLToPath } from "node:url";

import { expect, test, type Page } from "@playwright/test";

const here = path.dirname(fileURLToPath(import.meta.url));
const CSV = path.resolve(here, "../../api/tests/fixtures/files/vendas_latin1.csv");
const SHOTS = process.env.E2E_SHOTS;

async function shot(page: Page, name: string) {
  if (SHOTS) await page.screenshot({ path: path.join(SHOTS, `${name}.png`) });
}

async function newProjectWithSource(page: Page) {
  await page.goto("/");
  await page.getByRole("button", { name: "Novo projeto" }).first().click();
  await page.getByLabel("Nome do projeto").fill(`E2E dinâmica ${Date.now()}`);
  await page.getByRole("button", { name: "Confirmar" }).click();
  await page.getByRole("button", { name: "Importar arquivo" }).first().click();
  await page.getByTestId("file-input").setInputFiles(CSV);
  await page.getByRole("button", { name: "Avançar" }).click();
  await page.getByRole("button", { name: "Importar", exact: true }).click();
  await expect(page.getByText("Importado: 4 linhas.")).toBeVisible();
  await page.getByRole("dialog").getByRole("button", { name: "Fechar" }).last().click();
}

const library = (page: Page) => page.getByRole("complementary", { name: "Biblioteca" });
const sidebar = (page: Page) => page.getByRole("complementary", { name: "Configuração do nó" });
const preview = (page: Page) => page.getByRole("region", { name: "Prévia" });

async function addField(page: Page, field: string, zone: string) {
  await sidebar(page).getByRole("button", { name: field, exact: true }).click();
  await page.getByRole("menuitem", { name: zone }).click();
}

test("tabela dinâmica: UF × ativo com soma de valor", async ({ page }) => {
  await newProjectWithSource(page);
  await library(page).getByRole("button", { name: "Tabela dinâmica", exact: true }).click();
  await addField(page, "uf", "Linhas");
  await addField(page, "ativo", "Colunas");
  await addField(page, "valor", "Valores");
  await expect(sidebar(page).getByText("2 colunas geradas")).toBeVisible({ timeout: 15_000 });
  await expect(page.getByTestId("pivot-zone-rows")).toContainText("uf");
  await expect(preview(page)).toContainText("3 linhas · 3 colunas", { timeout: 15_000 });
  await shot(page, "10-pivot");
});

test("juntar uma tabela com ela mesma avisa sobre multiplicação de linhas", async ({ page }) => {
  await newProjectWithSource(page);
  const nodes = page.locator('[data-testid^="node-"]');
  await nodes.first().click();
  // Duplicate the source and join both copies on "uf" (PR appears twice -> rows multiply).
  await page.keyboard.press("Control+d");
  await library(page).getByRole("button", { name: "Juntar", exact: true }).click();
  await expect(nodes).toHaveCount(3);
  // The library wired the selected copy to the left input; wire the original to the right one
  // with the keyboard-accessible inputs picker (option 0 is "(nenhuma)", 1 is the original).
  const right = sidebar(page).getByLabel("Entrada direita");
  await right.selectOption({ index: 1 });
  await expect(page.locator(".react-flow__edge")).toHaveCount(2);
  await sidebar(page).getByRole("button", { name: "Chave" }).click();
  await expect(preview(page)).toContainText("6 linhas", { timeout: 15_000 });
  await expect(preview(page)).toContainText("multiplicou as linhas", { timeout: 15_000 });
  await shot(page, "11-join");
});
