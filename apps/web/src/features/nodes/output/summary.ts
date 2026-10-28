import type { OutputConfig } from "@/api/types";

export function summary(c: OutputConfig): string {
  const preset = c.format === "csv" && c.preset === "excel_br" ? " · Excel Brasil" : "";
  return `${c.filename}.${c.format}${preset}`;
}
