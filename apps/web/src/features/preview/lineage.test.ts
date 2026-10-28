import { describe, expect, it } from "vitest";

import type { Pipeline, SchemaResponse } from "@/api/types";

import { columnLineage } from "./lineage";

const cols = (...names: string[]) => names.map((name) => ({ name, type: "text" as const }));

const pipeline: Pipeline = {
  schema_version: 1,
  settings: { locale: "pt-BR", params: [] },
  nodes: [
    { id: "s", type: "source", config: { source_id: "src1" }, ui: { x: 0, y: 0, label: "Vendas" } },
    {
      id: "c",
      type: "calculated",
      config: { name: "receita", mode: "new", formula: "1" },
      ui: { x: 0, y: 0 },
    },
    {
      id: "r",
      type: "select",
      config: { mode: "drop", columns: [], renames: { receita: "faturamento" } },
      ui: { x: 0, y: 0 },
    },
  ],
  edges: [
    { id: "e1", source: "s", target: "c", source_handle: "out", target_handle: "in" },
    { id: "e2", source: "c", target: "r", source_handle: "out", target_handle: "in" },
  ],
};

const analysis: SchemaResponse = {
  nodes: {
    s: { status: "ok", columns: cols("uf"), issues: [], changed_columns: [], input_columns: {}, hash: "1" },
    c: {
      status: "ok",
      columns: cols("uf", "receita"),
      issues: [],
      changed_columns: ["receita"],
      input_columns: { in: cols("uf") },
      hash: "2",
    },
    r: {
      status: "ok",
      columns: cols("uf", "faturamento"),
      issues: [],
      changed_columns: ["faturamento"],
      input_columns: { in: cols("uf", "receita") },
      hash: "3",
    },
  },
};

describe("columnLineage", () => {
  it("follows renames back to the node that created the column", () => {
    const steps = columnLineage(pipeline, analysis, "r", "faturamento", () => "vendas.csv");
    expect(steps.map((s) => s.text)).toEqual([
      'criada em "Coluna calculada"',
      'renomeada em "Selecionar colunas" (era "receita")',
    ]);
  });

  it("traces a source column to its file", () => {
    const steps = columnLineage(pipeline, analysis, "r", "uf", () => "vendas.csv");
    expect(steps.map((s) => s.text)).toEqual(['vem do arquivo "vendas.csv"']);
  });
});
