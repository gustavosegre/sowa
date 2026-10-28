import type { LookupConfig } from "@/api/types";

export function summary(c: LookupConfig): string {
  const key = c.keys.map((k) => k.main).join(", ");
  return c.columns.length ? `${c.columns.join(", ")} por ${key || "—"}` : "Escolha as colunas";
}
