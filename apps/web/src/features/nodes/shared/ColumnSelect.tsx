import { Check, ChevronDown, Search } from "lucide-react";
import { useMemo, useState } from "react";

import type { Column } from "@/api/types";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui";
import { TypeIcon } from "@/components/TypeIcon";
import { t } from "@/i18n/pt-BR";
import { cn } from "@/lib/utils";

/** Column picker with search and type icons. Shows the current value even if it no longer exists. */
export function ColumnSelect({
  columns,
  value,
  onChange,
  placeholder = "Coluna…",
  className,
  allowEmpty = false,
}: {
  columns: Column[];
  value: string | null | undefined;
  onChange: (name: string) => void;
  placeholder?: string;
  className?: string;
  allowEmpty?: boolean;
}) {
  const [open, setOpen] = useState(false);
  const [q, setQ] = useState("");
  const current = columns.find((c) => c.name === value);
  const missing = Boolean(value) && !current;
  const filtered = useMemo(() => {
    const s = q.trim().toLowerCase();
    return s ? columns.filter((c) => c.name.toLowerCase().includes(s)) : columns;
  }, [columns, q]);

  return (
    <Popover open={open} onOpenChange={(o) => (setOpen(o), setQ(""))}>
      <PopoverTrigger asChild>
        <button
          type="button"
          className={cn(
            "flex h-8 w-full min-w-0 cursor-pointer items-center gap-1.5 rounded-md border border-input bg-card px-2 text-left text-[13px] outline-none focus-visible:ring-2 focus-visible:ring-ring/40",
            missing && "border-danger text-danger",
            className,
          )}
          aria-label={placeholder}
        >
          {current && <TypeIcon type={current.type} />}
          <span className={cn("min-w-0 flex-1 truncate", !value && "text-muted-foreground")}>
            {value || placeholder}
          </span>
          <ChevronDown className="size-3.5 shrink-0 text-muted-foreground" />
        </button>
      </PopoverTrigger>
      <PopoverContent className="w-64 p-1" align="start">
        <div className="flex items-center gap-1.5 border-b px-1.5 pb-1">
          <Search className="size-3.5 text-muted-foreground" />
          <input
            autoFocus
            value={q}
            onChange={(e) => setQ(e.target.value)}
            placeholder={t.common.search}
            className="h-7 w-full bg-transparent text-[13px] outline-none"
            onKeyDown={(e) => {
              const first = filtered[0];
              if (e.key === "Enter" && first) {
                onChange(first.name);
                setOpen(false);
              }
            }}
          />
        </div>
        <div className="max-h-64 overflow-auto py-1">
          {allowEmpty && (
            <button
              type="button"
              className="flex w-full items-center gap-2 rounded px-2 py-1 text-left text-[13px] text-muted-foreground hover:bg-muted"
              onClick={() => (onChange(""), setOpen(false))}
            >
              {t.common.none}
            </button>
          )}
          {filtered.map((c) => (
            <button
              type="button"
              key={c.name}
              className="flex w-full items-center gap-2 rounded px-2 py-1 text-left text-[13px] hover:bg-muted"
              onClick={() => (onChange(c.name), setOpen(false))}
            >
              <TypeIcon type={c.type} />
              <span className="min-w-0 flex-1 truncate">{c.name}</span>
              {c.name === value && <Check className="size-3.5 text-primary" />}
            </button>
          ))}
          {!filtered.length && <p className="px-2 py-2 text-xs text-muted-foreground">{t.palette.empty}</p>}
        </div>
      </PopoverContent>
    </Popover>
  );
}

/** Multi-select of columns as removable chips + picker. */
export function ColumnMultiSelect({
  columns,
  value,
  onChange,
  placeholder = "Adicionar coluna…",
}: {
  columns: Column[];
  value: string[];
  onChange: (v: string[]) => void;
  placeholder?: string;
}) {
  const remaining = columns.filter((c) => !value.includes(c.name));
  const names = new Set(columns.map((c) => c.name));
  return (
    <div className="flex flex-col gap-1.5">
      {value.length > 0 && (
        <div className="flex flex-wrap gap-1">
          {value.map((v) => (
            <span
              key={v}
              className={cn(
                "inline-flex items-center gap-1 rounded border bg-muted px-1.5 py-0.5 text-xs",
                !names.has(v) && "border-danger text-danger",
              )}
            >
              {v}
              <button
                type="button"
                aria-label={`${t.common.remove} ${v}`}
                className="cursor-pointer text-muted-foreground hover:text-foreground"
                onClick={() => onChange(value.filter((x) => x !== v))}
              >
                ×
              </button>
            </span>
          ))}
        </div>
      )}
      <ColumnSelect
        columns={remaining}
        value=""
        placeholder={placeholder}
        onChange={(n) => onChange([...value, n])}
      />
    </div>
  );
}
