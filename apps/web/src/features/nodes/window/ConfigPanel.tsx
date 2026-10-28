import { Plus, Trash2 } from "lucide-react";

import type { WindowConfig, WindowItem } from "@/api/types";
import { Button, Field, Input, SectionTitle, Select } from "@/components/ui";
import { t } from "@/i18n/pt-BR";

import { ColumnMultiSelect, ColumnSelect } from "../shared/ColumnSelect";
import type { ConfigPanelProps } from "../shared/panel";
import { SortKeysEditor } from "../shared/SortKeysEditor";

const tt = t.nodes2;
const NEEDS_COLUMN = new Set([
  "cumulative_sum",
  "previous",
  "next",
  "pct_of_total",
  "moving_avg",
  "partition_agg",
]);
const NUMERIC = new Set(["cumulative_sum", "pct_of_total", "moving_avg"]);
const FNS = Object.entries(tt.windowFns).map(([value, label]) => ({
  value: value as WindowItem["fn"],
  label,
}));
const AGGS = Object.entries(t.aggs).map(([value, label]) => ({ value: value as WindowItem["agg"], label }));

export function ConfigPanel({ config, update, columns }: ConfigPanelProps<WindowConfig>) {
  const setItem = (i: number, patch: Partial<WindowItem>) =>
    update({ ...config, items: config.items.map((it, j) => (j === i ? { ...it, ...patch } : it)) });
  const numeric = columns.filter((c) => c.type === "integer" || c.type === "decimal");
  return (
    <div className="flex flex-col gap-3">
      <Field label={tt.partitionBy}>
        <ColumnMultiSelect
          columns={columns}
          value={config.partition_by}
          onChange={(partition_by) => update({ ...config, partition_by })}
        />
      </Field>
      <div className="flex flex-col gap-1">
        <span className="text-xs font-medium text-muted-foreground">{tt.orderBy}</span>
        <SortKeysEditor
          columns={columns}
          value={config.order_by}
          onChange={(order_by) => update({ ...config, order_by })}
        />
      </div>
      <SectionTitle>{tt.calculations}</SectionTitle>
      {config.items.map((it, i) => (
        <div key={i} className="flex flex-col gap-1.5 rounded-md border p-2">
          <div className="flex items-center gap-1.5">
            <Select value={it.fn} options={FNS} onChange={(fn) => setItem(i, { fn })} />
            <Button
              variant="ghost"
              size="iconSm"
              aria-label={t.common.remove}
              onClick={() => update({ ...config, items: config.items.filter((_, j) => j !== i) })}
            >
              <Trash2 />
            </Button>
          </div>
          {it.fn === "partition_agg" && (
            <Select value={it.agg} options={AGGS} onChange={(agg) => setItem(i, { agg })} />
          )}
          {NEEDS_COLUMN.has(it.fn) && (
            <ColumnSelect
              columns={NUMERIC.has(it.fn) ? numeric : columns}
              value={it.column}
              onChange={(column) => setItem(i, { column })}
            />
          )}
          {(it.fn === "previous" || it.fn === "next") && (
            <Field label={tt.offset}>
              <Input
                type="number"
                min={1}
                value={it.offset}
                onChange={(e) => setItem(i, { offset: Math.max(1, Number(e.target.value) || 1) })}
              />
            </Field>
          )}
          {it.fn === "moving_avg" && (
            <Field label={tt.windowSize}>
              <Input
                type="number"
                min={1}
                value={it.size}
                onChange={(e) => setItem(i, { size: Math.max(1, Number(e.target.value) || 1) })}
              />
            </Field>
          )}
          <Input
            className="h-7"
            value={it.as}
            placeholder={it.column ? `${it.fn}_${it.column}` : it.fn}
            onChange={(e) => setItem(i, { as: e.target.value })}
            aria-label={t.nodes.groupBy.as}
          />
        </div>
      ))}
      <Button
        variant="outline"
        size="sm"
        className="self-start"
        onClick={() =>
          update({
            ...config,
            items: [
              ...config.items,
              {
                fn: "cumulative_sum",
                column: numeric[0]?.name ?? null,
                as: "",
                offset: 1,
                size: 3,
                agg: "sum",
              },
            ],
          })
        }
      >
        <Plus /> {tt.addCalc}
      </Button>
    </div>
  );
}
