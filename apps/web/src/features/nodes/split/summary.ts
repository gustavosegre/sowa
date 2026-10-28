import type { SplitConfig } from "@/api/types";

export function summary(c: SplitConfig): string {
  if (!c.column) return "Escolha a coluna";
  if (c.mode === "delimiter") return `${c.column} por "${c.delimiter}" em ${c.parts} partes`;
  if (c.mode === "position") return `${c.column} nas posições ${c.positions.join(", ")}`;
  return `${c.column} por regex`;
}
