import type { SubflowConfig } from "@/api/types";
import { t } from "@/i18n/pt-BR";

export function summary(c: SubflowConfig): string {
  return t.templates.summary(c.flow.nodes.length, c.flow.inputs.length);
}
