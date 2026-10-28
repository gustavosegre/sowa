import type { SqlConfig } from "@/api/types";

export function summary(c: SqlConfig): string {
  const flat = c.query.replace(/\s+/g, " ").trim();
  return flat.length > 70 ? `${flat.slice(0, 67)}…` : flat;
}
