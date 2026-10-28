import type { SortConfig } from "@/api/types";

export function summary(c: SortConfig): string {
  if (!c.keys.length) return "Sem ordenação";
  return c.keys.map((k) => `${k.column} ${k.direction === "asc" ? "↑" : "↓"}`).join(", ");
}
