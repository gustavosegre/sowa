import type { BinConfig } from "@/api/types";

export function summary(c: BinConfig): string {
  if (!c.column) return "Escolha a coluna";
  if (c.mode === "equal") return `${c.column} em ${c.count} faixas iguais`;
  return `${c.column}: limites ${c.boundaries.map((b) => b.toLocaleString("pt-BR")).join("; ") || "—"}`;
}
