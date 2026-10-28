import {
  Calendar,
  CalendarClock,
  CaseSensitive,
  Clock,
  Hash,
  HelpCircle,
  ToggleLeft,
  type LucideIcon,
} from "lucide-react";

import type { LogicalType } from "@/api/types";
import { t } from "@/i18n/pt-BR";
import { cn } from "@/lib/utils";

const ICONS: Record<LogicalType, LucideIcon | null> = {
  text: CaseSensitive,
  integer: Hash,
  decimal: null,
  boolean: ToggleLeft,
  date: Calendar,
  datetime: CalendarClock,
  time: Clock,
  other: HelpCircle,
};

export function TypeIcon({ type, className }: { type: LogicalType; className?: string }) {
  const Icon = ICONS[type];
  const label = t.types[type] ?? type;
  if (Icon === null) {
    return (
      <span
        title={label}
        aria-hidden
        className={cn(
          "inline-flex w-3.5 shrink-0 justify-center font-mono text-[9px] font-bold text-muted-foreground",
          className,
        )}
      >
        1,2
      </span>
    );
  }
  return (
    <span title={label} aria-hidden className="inline-flex shrink-0">
      <Icon className={cn("size-3.5 text-muted-foreground", className)} aria-hidden />
    </span>
  );
}

export const TYPE_OPTIONS: { value: LogicalType; label: string }[] = (
  ["text", "integer", "decimal", "boolean", "date", "datetime", "time"] as LogicalType[]
).map((v) => ({ value: v, label: t.types[v] ?? v }));
