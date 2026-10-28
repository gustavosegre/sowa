import type { Condition, ConditionGroup, FilterConfig } from "@/api/types";
import { t } from "@/i18n/pt-BR";

const SYMBOL: Record<string, string> = { eq: "=", neq: "≠", gt: ">", gte: "≥", lt: "<", lte: "≤" };

function cond(c: Condition): string {
  const op = SYMBOL[c.operator];
  if (op) return `${c.column} ${op} ${String(c.value ?? "")}`;
  if (c.operator === "between")
    return `${c.column} entre ${String(c.value ?? "")} e ${String(c.value2 ?? "")}`;
  if (c.operator === "in" || c.operator === "not_in")
    return `${c.column} ${t.operators[c.operator] ?? ""} (${c.values.map(String).join("; ")})`;
  const label = t.operators[c.operator] ?? c.operator;
  return c.value != null && c.value !== ""
    ? `${c.column} ${label} "${String(c.value)}"`
    : `${c.column} ${label}`;
}

function group(g: ConditionGroup, nested = false): string {
  const parts = g.conditions.map((c) => (c.kind === "group" ? group(c, true) : cond(c)));
  const text = parts.join(g.op === "and" ? " e " : " ou ");
  return nested && parts.length > 1 ? `(${text})` : text;
}

export function summary(c: FilterConfig): string {
  if (c.mode === "formula") return c.formula.trim() ? `Filtro: ${c.formula}` : "Sem condição";
  const text = group(c.rules);
  return text ? `Filtro: ${text}` : "Sem condição";
}
