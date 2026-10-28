import { type ClassValue, clsx } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]): string {
  return twMerge(clsx(inputs));
}

const intFmt = new Intl.NumberFormat("pt-BR");

export function fmtInt(n: number | null | undefined): string {
  return n == null ? "—" : intFmt.format(n);
}

export function fmtBytes(n: number): string {
  if (n < 1024) return `${n} B`;
  const units = ["KB", "MB", "GB"];
  let v = n / 1024;
  let i = 0;
  while (v >= 1024 && i < units.length - 1) {
    v /= 1024;
    i++;
  }
  return `${v.toLocaleString("pt-BR", { maximumFractionDigits: 1 })} ${units[i] ?? "GB"}`;
}

export function fmtDateTime(iso: string): string {
  return new Date(iso).toLocaleString("pt-BR", { dateStyle: "short", timeStyle: "short" });
}

let counter = 0;
export function uid(prefix = "n"): string {
  counter = (counter + 1) % 1000;
  return `${prefix}_${Date.now().toString(36)}${counter.toString(36)}${Math.random().toString(36).slice(2, 5)}`;
}

export function debounce<A extends unknown[]>(fn: (...args: A) => void, ms: number): (...args: A) => void {
  let h: ReturnType<typeof setTimeout> | undefined;
  return (...args: A) => {
    if (h) clearTimeout(h);
    h = setTimeout(() => fn(...args), ms);
  };
}
