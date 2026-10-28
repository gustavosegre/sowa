import { Plus, Trash2 } from "lucide-react";

import type { SortConfig, SortKey } from "@/api/types";
import { Button, Select } from "@/components/ui";
import { t } from "@/i18n/pt-BR";

import { ColumnSelect } from "../shared/ColumnSelect";
import type { ConfigPanelProps } from "../shared/panel";

export function newSortKey(column: string, direction: SortKey["direction"] = "asc"): SortKey {
  return { column, direction, nulls: "last", case_sensitive: false };
}

export function ConfigPanel({ config, update, columns }: ConfigPanelProps<SortConfig>) {
  const tt = t.nodes.sort;
  const setKey = (i: number, patch: Partial<SortKey>) =>
    update({ ...config, keys: config.keys.map((k, j) => (j === i ? { ...k, ...patch } : k)) });
  return (
    <div className="flex flex-col gap-2">
      {config.keys.map((k, i) => (
        <div key={i} className="flex flex-col gap-1.5 rounded-md border p-2">
          <div className="flex items-center gap-1.5">
            <span className="w-4 text-center text-[11px] text-muted-foreground">{i + 1}</span>
            <ColumnSelect columns={columns} value={k.column} onChange={(column) => setKey(i, { column })} />
            <Button
              variant="ghost"
              size="iconSm"
              aria-label={t.common.remove}
              onClick={() => update({ ...config, keys: config.keys.filter((_, j) => j !== i) })}
            >
              <Trash2 />
            </Button>
          </div>
          <div className="grid grid-cols-2 gap-1.5 pl-5">
            <Select
              value={k.direction}
              options={[
                { value: "asc", label: tt.asc },
                { value: "desc", label: tt.desc },
              ]}
              onChange={(direction) => setKey(i, { direction })}
            />
            <Select
              value={k.nulls}
              options={[
                { value: "last", label: tt.nullsLast },
                { value: "first", label: tt.nullsFirst },
              ]}
              onChange={(nulls) => setKey(i, { nulls })}
            />
          </div>
        </div>
      ))}
      <Button
        variant="outline"
        size="sm"
        className="self-start"
        onClick={() => update({ ...config, keys: [...config.keys, newSortKey(columns[0]?.name ?? "")] })}
      >
        <Plus /> {tt.addKey}
      </Button>
    </div>
  );
}
