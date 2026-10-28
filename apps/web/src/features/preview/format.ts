import type { LogicalType } from "@/api/types";

const DEC = new Intl.NumberFormat("pt-BR", { maximumFractionDigits: 10 });
const INT = new Intl.NumberFormat("pt-BR");

function asText(v: unknown): string {
  if (typeof v === "string") return v;
  if (typeof v === "number" || typeof v === "bigint" || typeof v === "boolean") return v.toString();
  return JSON.stringify(v) ?? "";
}

function pad(n: number): string {
  return n.toString().padStart(2, "0");
}

/** Dates arrive as epoch ms (or Date); render in UTC so a DATE never shifts a day. */
function toDate(v: unknown): Date | null {
  if (v instanceof Date) return v;
  if (typeof v === "number") return new Date(v);
  if (typeof v === "bigint") return new Date(Number(v));
  return null;
}

export function formatCell(v: unknown, type: LogicalType): string {
  if (v === null || v === undefined) return "";
  switch (type) {
    case "integer":
      return typeof v === "bigint" ? v.toLocaleString("pt-BR") : INT.format(Number(v));
    case "decimal":
      return Number.isFinite(Number(v)) ? DEC.format(Number(v)) : asText(v);
    case "boolean":
      return v ? "verdadeiro" : "falso";
    case "date": {
      const d = toDate(v);
      return d ? `${pad(d.getUTCDate())}/${pad(d.getUTCMonth() + 1)}/${d.getUTCFullYear()}` : asText(v);
    }
    case "datetime": {
      const d = toDate(v);
      return d
        ? `${pad(d.getUTCDate())}/${pad(d.getUTCMonth() + 1)}/${d.getUTCFullYear()} ${pad(d.getUTCHours())}:${pad(d.getUTCMinutes())}:${pad(d.getUTCSeconds())}`
        : asText(v);
    }
    case "time": {
      // Arrow time64 (microseconds since midnight) or a string.
      if (typeof v === "bigint" || typeof v === "number") {
        const total = Math.floor(Number(v) / 1_000_000);
        return `${pad(Math.floor(total / 3600))}:${pad(Math.floor((total % 3600) / 60))}:${pad(total % 60)}`;
      }
      return asText(v);
    }
    default:
      return asText(v);
  }
}

/** Value as typed in a filter condition (dates as dd/mm/aaaa, decimals with comma). */
export function filterValue(v: unknown, type: LogicalType): string {
  if (type === "integer" || type === "decimal") return formatCell(v, type).replace(/\./g, "");
  return formatCell(v, type);
}
