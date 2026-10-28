import type { SourceConfig } from "@/api/types";
import { fmtInt } from "@/lib/utils";

export function summary(c: SourceConfig): string {
  if (!c.source_id) return "Nenhum arquivo escolhido";
  if (c.sample) {
    const how = c.sample.mode === "first" ? "primeiras" : "aleatórias";
    return `Amostra: ${fmtInt(c.sample.rows)} linhas ${how}`;
  }
  return "";
}
