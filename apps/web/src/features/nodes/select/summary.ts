import type { SelectConfig } from "@/api/types";

export function summary(c: SelectConfig): string {
  const renames = Object.keys(c.renames).length;
  const parts: string[] = [];
  if (c.mode === "keep") parts.push(`Manter ${c.columns.length} colunas`);
  else if (c.columns.length) parts.push(`Remover ${c.columns.join(", ")}`);
  if (renames) parts.push(`${renames} renomeada${renames > 1 ? "s" : ""}`);
  return parts.join(" · ") || "Todas as colunas";
}
