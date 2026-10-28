import type { PivotConfig } from "@/api/types";

export function summary(c: PivotConfig): string {
  const rows = c.rows.map((r) => r.column).join(", ") || "—";
  const cols = c.columns ? ` × ${c.columns.column}` : "";
  return `${rows}${cols}: ${c.values.length} valor${c.values.length === 1 ? "" : "es"}`;
}
