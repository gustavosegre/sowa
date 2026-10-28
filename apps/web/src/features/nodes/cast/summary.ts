import type { CastConfig } from "@/api/types";
import { t } from "@/i18n/pt-BR";

export function summary(c: CastConfig): string {
  if (!c.casts.length) return "Nenhuma conversão";
  return c.casts.map((r) => `${r.column} → ${t.types[r.to] ?? r.to}`).join(", ");
}
