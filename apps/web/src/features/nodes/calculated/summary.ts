import type { CalculatedConfig } from "@/api/types";

export function summary(c: CalculatedConfig): string {
  if (!c.formula.trim()) return `${c.name} = …`;
  const f = c.formula.length > 60 ? `${c.formula.slice(0, 57)}…` : c.formula;
  return `${c.name} = ${f}`;
}
