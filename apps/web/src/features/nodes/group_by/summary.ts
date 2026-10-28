import type { GroupByConfig } from "@/api/types";
import { t } from "@/i18n/pt-BR";

export function summary(c: GroupByConfig): string {
  const aggs = c.aggs.map((a) =>
    a.fn === "count" ? "contagem" : `${(t.aggs[a.fn] ?? a.fn).toLowerCase()} de ${a.column ?? ""}`,
  );
  const what = [...aggs, ...c.measures.map((m) => m.name)].join(", ") || "sem agregações";
  return c.keys.length ? `Por ${c.keys.join(", ")}: ${what}` : `Total: ${what}`;
}
