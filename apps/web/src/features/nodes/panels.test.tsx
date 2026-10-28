import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import type { Column, PipelineNode, SelectConfig, SortConfig } from "@/api/types";

import { summary as filterSummary } from "./filter/summary";
import { summary as groupBySummary } from "./group_by/summary";
import { ConfigPanel as SelectPanel } from "./select/ConfigPanel";
import { ConfigPanel as SortPanel } from "./sort/ConfigPanel";

const columns: Column[] = [
  { name: "uf", type: "text" },
  { name: "valor", type: "decimal" },
  { name: "data", type: "date" },
];

const node = (type: string, config: Record<string, unknown>): PipelineNode => ({
  id: "n1",
  type,
  config,
  ui: { x: 0, y: 0 },
});

describe("SortPanel", () => {
  it("adds a sort key using the first input column", async () => {
    const update = vi.fn();
    const config: SortConfig = { keys: [] };
    render(<SortPanel node={node("sort", config)} config={config} update={update} columns={columns} />);
    await userEvent.click(screen.getByRole("button", { name: /Adicionar ordenação/ }));
    expect(update).toHaveBeenCalledWith({
      keys: [{ column: "uf", direction: "asc", nulls: "last", case_sensitive: false }],
    });
  });

  it("changes the direction of a key", async () => {
    const update = vi.fn();
    const config: SortConfig = {
      keys: [{ column: "valor", direction: "asc", nulls: "last", case_sensitive: false }],
    };
    render(<SortPanel node={node("sort", config)} config={config} update={update} columns={columns} />);
    await userEvent.selectOptions(screen.getAllByRole("combobox")[0] as HTMLSelectElement, "desc");
    expect(update).toHaveBeenCalledWith({
      keys: [{ column: "valor", direction: "desc", nulls: "last", case_sensitive: false }],
    });
  });
});

describe("SelectPanel", () => {
  it("unchecking a column in drop mode removes it", async () => {
    const update = vi.fn();
    const config: SelectConfig = { mode: "drop", columns: [], renames: {} };
    render(<SelectPanel node={node("select", config)} config={config} update={update} columns={columns} />);
    const boxes = screen.getAllByRole("checkbox");
    expect(boxes).toHaveLength(3);
    await userEvent.click(boxes[1] as HTMLElement);
    expect(update).toHaveBeenCalledWith({ mode: "drop", columns: ["valor"], renames: {} });
  });

  it("reordering switches to keep mode with an explicit order", async () => {
    const update = vi.fn();
    const config: SelectConfig = { mode: "drop", columns: [], renames: {} };
    render(<SelectPanel node={node("select", config)} config={config} update={update} columns={columns} />);
    await userEvent.click(screen.getAllByRole("button", { name: "Subir" })[1] as HTMLElement);
    expect(update).toHaveBeenCalledWith({ mode: "keep", columns: ["valor", "uf", "data"], renames: {} });
  });

  it("highlights a selected column that no longer exists upstream", () => {
    const config: SelectConfig = { mode: "keep", columns: ["sumiu"], renames: {} };
    render(<SelectPanel node={node("select", config)} config={config} update={vi.fn()} columns={columns} />);
    expect(screen.getByTitle("sumiu")).toHaveClass("text-danger");
  });
});

describe("summaries", () => {
  it("describes filters like the CLAUDE.md example", () => {
    expect(
      filterSummary({
        mode: "rules",
        formula: "",
        rules: {
          kind: "group",
          op: "and",
          conditions: [
            {
              kind: "condition",
              column: "UF",
              operator: "eq",
              value: "PR",
              value2: null,
              values: [],
              case_sensitive: false,
            },
            {
              kind: "condition",
              column: "valor",
              operator: "gt",
              value: 100,
              value2: null,
              values: [],
              case_sensitive: false,
            },
          ],
        },
      }),
    ).toBe("Filtro: UF = PR e valor > 100");
  });

  it("describes group by", () => {
    expect(
      groupBySummary({
        keys: ["uf"],
        aggs: [{ column: "receita", fn: "sum", as: "", percentile: 0.5, separator: ", ", order_by: null }],
        measures: [],
      }),
    ).toBe("Por uf: soma de receita");
  });
});
