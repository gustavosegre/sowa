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

test("parâmetros, nó SQL e histórico de versões", async ({ page }) => {
  await page.goto("/");
  await page.getByRole("button", { name: "Novo projeto" }).first().click();
  await page.getByLabel("Nome do projeto").fill(`E2E fase 3 ${Date.now()}`);
  await page.getByRole("button", { name: "Confirmar" }).click();
  await page.getByRole("button", { name: "Importar arquivo" }).first().click();
  await page.getByTestId("file-input").setInputFiles(CSV);
  await page.getByRole("button", { name: "Avançar" }).click();
  await page.getByRole("button", { name: "Importar", exact: true }).click();
  await page.getByRole("dialog").getByRole("button", { name: "Fechar" }).last().click();

  // Global parameter {meta} used in a formula.
  await page.getByRole("button", { name: "Parâmetros" }).click();
  await page.getByRole("button", { name: "Parâmetro" }).click();
  await page.getByLabel("Nome", { exact: true }).fill("meta");
  await page.getByLabel("Tipo", { exact: true }).selectOption("decimal");
  await page.getByLabel("Valor", { exact: true }).fill("5");
  await page.getByRole("button", { name: "Salvar" }).click();

  await library(page).getByRole("button", { name: "Coluna calculada", exact: true }).click();
  await sidebar(page).getByLabel("Nome da coluna").fill("acima_da_meta");
  await sidebar(page).getByRole("textbox", { name: "Fórmula" }).click();
  await page.keyboard.type("[valor] > {meta}");
  await page.keyboard.press("Escape");
  await expect(sidebar(page).getByText("Booleano", { exact: true })).toBeVisible({ timeout: 10_000 });
  await expect(preview(page)).toContainText("9 colunas", { timeout: 15_000 });
  await shot(page, "12-param");

  // SQL node after it.
  await library(page).getByRole("button", { name: "SQL", exact: true }).click();
  const query = sidebar(page).getByLabel("Consulta SQL (DuckDB)");
  await query.fill(
    "SELECT uf, COUNT(*) AS n, SUM(CASE WHEN acima_da_meta THEN 1 ELSE 0 END) AS acima\nFROM input\nGROUP BY uf\nORDER BY uf",
  );
  await expect(preview(page)).toContainText("3 linhas", { timeout: 15_000 });
  await expect(sidebar(page).getByText("input", { exact: true })).toBeVisible();
  await shot(page, "13-sql");

  // A forbidden query is a node error, not a crash.
  await query.fill("SELECT * FROM read_csv('C:/Windows/win.ini')");
  await expect(sidebar(page)).toContainText("Funções de tabela não são permitidas", { timeout: 10_000 });

  // Named version in the history.
  await page.getByRole("button", { name: "Histórico" }).click();
  await page.getByLabel("Nome da versão (ex.: Entrega de março)").fill("Marco 1");
  await page.getByRole("button", { name: "Salvar versão" }).click();
  await expect(page.getByRole("dialog")).toContainText("Marco 1");
  await shot(page, "14-versions");
});
