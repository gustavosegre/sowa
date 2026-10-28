import type { ConditionalConfig } from "@/api/types";

export function summary(c: ConditionalConfig): string {
  return `${c.name}: ${c.rules.length} regra${c.rules.length === 1 ? "" : "s"} SE`;
}
