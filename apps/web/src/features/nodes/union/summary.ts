import type { UnionConfig } from "@/api/types";

export function summary(c: UnionConfig): string {
  return c.mode === "by_name" ? "Alinhar por nome" : "Alinhar por posição";
}
