import { Plus, Trash2 } from "lucide-react";

import type { Column, SortKey } from "@/api/types";
import { Button, Select } from "@/components/ui";
import { t } from "@/i18n/pt-BR";

import { ColumnSelect } from "./ColumnSelect";

/** Compact list of sort keys (column + direction), used by distinct, fill_null and window. */
export function SortKeysEditor({
  columns,
  value,
  onChange,
}: {
  columns: Column[];
  value: SortKey[];
  onChange: (v: SortKey[]) => void;
}) {
  const set = (i: number, patch: Partial<SortKey>) =>
    onChange(value.map((k, j) => (j === i ? { ...k, ...patch } : k)));
  return (
    <div className="flex flex-col gap-1.5">
      {value.map((k, i) => (
        <div key={i} className="flex items-center gap-1.5">
          <ColumnSelect columns={columns} value={k.column} onChange={(column) => set(i, { column })} />
          <Select
            className="w-32 shrink-0"
            value={k.direction}
            options={[
              { value: "asc", label: t.nodes.sort.asc },
              { value: "desc", label: t.nodes.sort.desc },
            ]}
            onChange={(direction) => set(i, { direction })}
          />
          <Button
            variant="ghost"
            size="iconSm"
            aria-label={t.common.remove}
            onClick={() => onChange(value.filter((_, j) => j !== i))}
          >
            <Trash2 />
          </Button>
        </div>
      ))}
      <Button
        variant="ghost"
        size="sm"
        className="self-start"
        onClick={() =>
          onChange([
            ...value,
            { column: columns[0]?.name ?? "", direction: "asc", nulls: "last", case_sensitive: false },
          ])
        }
      >
        <Plus /> {t.nodes2.addOrder}
      </Button>
    </div>
  );
}

/** Parse "1; 2,5; 10" (pt-BR numbers) into numbers, ignoring invalid pieces. */
export function parseNumberList(text: string): number[] {
  return text
    .split(";")
    .map((x) => x.trim().replace(/\./g, "").replace(",", "."))
    .filter((x) => x !== "" && !Number.isNaN(Number(x)))
    .map(Number);
}

export function formatNumberList(values: number[]): string {
  return values
    .map((v) => v.toLocaleString("pt-BR", { maximumFractionDigits: 10, useGrouping: false }))
    .join("; ");
}
