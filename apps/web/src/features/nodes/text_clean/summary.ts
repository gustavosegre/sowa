import type { TextCleanConfig } from "@/api/types";

export function summary(c: TextCleanConfig): string {
  if (!c.columns.length) return "Nenhuma coluna";
  const ops = [
    c.trim && "aparar",
    c.case !== "none" &&
      ({ upper: "MAIÚSCULAS", lower: "minúsculas", title: "Iniciais" } as Record<string, string>)[c.case],
    c.remove_accents && "sem acentos",
  ].filter(Boolean);
  return `${c.columns.join(", ")}: ${ops.join(", ") || "sem mudanças"}`;
}
