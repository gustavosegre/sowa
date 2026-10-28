import type { DistinctConfig } from "@/api/types";

export function summary(c: DistinctConfig): string {
  if (!c.keys.length) return "Linhas inteiras repetidas";
  const keep = c.keep === "first" ? "primeira" : "última";
  return `Por ${c.keys.join(", ")} · mantém a ${keep}`;
}
