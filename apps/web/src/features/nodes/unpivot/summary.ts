import type { UnpivotConfig } from "@/api/types";

export function summary(c: UnpivotConfig): string {
  return c.columns.length
    ? `${c.columns.length} colunas → ${c.name_column}, ${c.value_column}`
    : "Escolha as colunas";
}
