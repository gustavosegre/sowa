import type { FillNullConfig } from "@/api/types";

export function summary(c: FillNullConfig): string {
  const how: Record<string, string> = {
    value: "valor",
    previous: "anterior",
    next: "próximo",
    mean: "média",
    median: "mediana",
  };
  return (
    c.rules
      .map(
        (r) => `${r.column} ← ${r.method === "value" ? String(r.value ?? "") : (how[r.method] ?? r.method)}`,
      )
      .join(", ") || "Sem regras"
  );
}
