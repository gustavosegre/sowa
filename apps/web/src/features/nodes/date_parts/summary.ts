import type { DatePartsConfig } from "@/api/types";

export function summary(c: DatePartsConfig): string {
  return c.column ? `${c.column}: ${c.parts.length} partes` : "Escolha a coluna de data";
}
