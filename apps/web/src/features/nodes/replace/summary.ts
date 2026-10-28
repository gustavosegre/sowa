import type { ReplaceConfig } from "@/api/types";

export function summary(c: ReplaceConfig): string {
  if (!c.column) return "Escolha a coluna";
  const first = c.rules[0];
  if (!first) return `${c.column}: sem regras`;
  const more = c.rules.length > 1 ? ` (+${c.rules.length - 1})` : "";
  return `${c.column}: "${String(first.find ?? "vazio")}" → "${String(first.replace ?? "")}"${more}`;
}
