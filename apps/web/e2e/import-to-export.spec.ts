import { readFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

import { expect, test, type Page } from "@playwright/test";

const here = path.dirname(fileURLToPath(import.meta.url));
const CSV = path.resolve(here, "../../api/tests/fixtures/files/vendas_latin1.csv");
const SHOTS = process.env.E2E_SHOTS;

async function shot(page: Page, name: string) {
  if (SHOTS) await page.screenshot({ path: path.join(SHOTS, `${name}.png`) });
}

async function addFromLibrary(page: Page, label: string) {
  await page
    .getByRole("complementary", { name: "Biblioteca" })
    .getByRole("button", { name: label, exact: true })
    .click();
}

test("CSV brasileiro → tipo → calculada → agrupar → exportar Excel Brasil", async ({ page }) => {
  await page.goto("/");
  await page.getByRole("button", { name: "Novo projeto" }).first().click();
  await page.getByLabel("Nome do projeto").fill(`E2E ${Date.now()}`);
  await page.getByRole("button", { name: "Confirmar" }).click();
  await expect(page.getByText("Comece importando um arquivo")).toBeVisible();
  await shot(page, "01-empty-editor");

  // Import wizard: file -> detected settings -> column types.
  await page.getByRole("button", { name: "Importar arquivo" }).first().click();
  await page.getByTestId("file-input").setInputFiles(CSV);
  await expect(page.getByLabel("Codificação")).toHaveValue("cp1252");
  await expect(page.getByLabel("Delimitador")).toHaveValue(";");
  await expect(page.getByLabel("Separador decimal")).toHaveValue(",");
  await expect(page.getByRole("dialog")).toContainText("Florianópolis");
  await shot(page, "02-wizard-settings");
  await page.getByRole("button", { name: "Avançar" }).click();
  await shot(page, "03-wizard-types");
  await page.getByRole("button", { name: "Importar", exact: true }).click();
  await expect(page.getByText("Importado: 4 linhas.")).toBeVisible();
  await page.getByRole("dialog").getByRole("button", { name: "Fechar" }).last().click();

  // The source node is on the canvas and selected; the preview shows its data.
  const source = page.locator('[data-testid^="node-"]').first();
  await expect(source).toBeVisible();
  await expect(page.getByText("4 linhas").first()).toBeVisible();
  await shot(page, "04-source-preview");

  // Alterar tipo: data_venda -> Data (dd/mm/aaaa). One value is broken on purpose.
  await addFromLibrary(page, "Alterar tipo");
  await page.getByRole("button", { name: "Adicionar conversão" }).click();
  const sidebar = page.getByRole("complementary", { name: "Configuração do nó" });
  await sidebar
    .getByRole("button", { name: "Coluna…" })
    .or(sidebar.getByRole("button", { name: "uf" }))
    .first()
    .click();
  await page.getByRole("button", { name: "data_venda" }).click();
  await sidebar.locator("select").first().selectOption("date");
  await expect(page.getByText(/1 valor não convertido em "data_venda"/)).toBeVisible({ timeout: 15_000 });
  await shot(page, "05-cast-warning");

  // Coluna calculada: receita = [preço] * [quantidade]
  await addFromLibrary(page, "Coluna calculada");
  await sidebar.getByLabel("Nome da coluna").fill("receita");
  const formula = sidebar.getByRole("textbox", { name: "Fórmula" });
  await formula.click();
  await page.keyboard.type("[preço] * [quantidade]");
  await page.keyboard.press("Escape");
  await expect(sidebar.getByText("Decimal", { exact: true })).toBeVisible({ timeout: 10_000 });
  await shot(page, "06-calculated");

  // Agrupar por UF somando a receita.
  await addFromLibrary(page, "Agrupar");
  await sidebar.getByRole("button", { name: "Adicionar coluna…" }).click();
  await page.getByRole("button", { name: "uf", exact: true }).click();
  await sidebar.getByRole("button", { name: "Agregação" }).click();
  await sidebar.locator("select").first().selectOption("sum");
  await sidebar
    .getByRole("button", { name: /Coluna…|quantidade|preço/ })
    .first()
    .click();
  await page.getByRole("button", { name: "receita" }).click();
  await sidebar.getByLabel("Nome", { exact: true }).first().fill("receita_total");
  await expect(page.getByText("3 linhas").first()).toBeVisible({ timeout: 15_000 });
  await shot(page, "07-group-by");

  // Exportar com o preset Excel Brasil (padrão do nó).
  await addFromLibrary(page, "Exportar");
  await sidebar.getByLabel("Nome do arquivo").fill("vendas_por_uf");
  await expect(page.getByTestId("save-status")).toHaveText(/Salvo/, { timeout: 10_000 });
  await sidebar.getByRole("button", { name: "Exportar" }).click();
  const link = sidebar.getByRole("link", { name: "Baixar arquivo" });
  await expect(link).toBeVisible({ timeout: 20_000 });
  await shot(page, "08-exported");
  const [download] = await Promise.all([page.waitForEvent("download"), link.click()]);
  const file = await download.path();
  const bytes = readFileSync(file);
  expect(bytes.subarray(0, 3)).toEqual(Buffer.from([0xef, 0xbb, 0xbf]));
  const lines = bytes
    .toString("utf-8")
    .replace(/^\uFEFF/, "")
    .trim()
    .split(/\r?\n/);
  expect(lines[0]).toBe("uf;receita_total");
  expect(lines).toContain("PR;3903,48");
  expect(lines).toContain("SC;0");
});
