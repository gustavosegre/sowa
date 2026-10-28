import type { WindowConfig } from "@/api/types";

export function summary(c: WindowConfig): string {
  const names = c.items.map((i) => i.as || i.fn).join(", ");
  const part = c.partition_by.length ? ` por ${c.partition_by.join(", ")}` : "";
  return names ? `${names}${part}` : "Sem cálculos";
}
