import type { SampleNodeConfig } from "@/api/types";
import { fmtInt } from "@/lib/utils";

export function summary(c: SampleNodeConfig): string {
  if (c.mode === "first") return `Primeiras ${fmtInt(c.rows)} linhas`;
  if (c.mode === "random") return `${fmtInt(c.rows)} linhas aleatórias`;
  return `${c.percent.toLocaleString("pt-BR")}% das linhas`;
}
