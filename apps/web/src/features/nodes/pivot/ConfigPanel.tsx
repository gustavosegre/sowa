import {
  DndContext,
  KeyboardSensor,
  PointerSensor,
  useDraggable,
  useDroppable,
  useSensor,
  useSensors,
  type DragEndEvent,
} from "@dnd-kit/core";
import { GripVertical, RefreshCw, X } from "lucide-react";
import { useEffect, useRef, useState, type ReactNode } from "react";

import { ApiError } from "@/api/client";
import { fetchPivotValues } from "@/api/hooks";
import type { Column, Condition, PivotConfig, PivotField, PivotValue } from "@/api/types";
import {
  Button,
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuTrigger,
  Field,
  Input,
  Select,
  Spinner,
  Switch,
} from "@/components/ui";
import { TypeIcon } from "@/components/TypeIcon";
import { t } from "@/i18n/pt-BR";
import { cn } from "@/lib/utils";
import { usePipelineStore } from "@/stores/pipelineStore";

import { newCondition } from "../filter/ConfigPanel";
import type { ConfigPanelProps } from "../shared/panel";

const tp = t.nodes2.pivot;
type Zone = "filters" | "rows" | "columns" | "values";
const ZONES: Zone[] = ["filters", "columns", "rows", "values"];
const MAX_VALUES = 200;
const AGG_FNS = Object.entries(t.aggs).map(([value, label]) => ({ value: value as PivotValue["fn"], label }));
const SHOW_AS: { value: PivotValue["show_as"]; label: string }[] = [
  { value: "normal", label: tp.showNormal },
  { value: "pct_total", label: tp.showPctTotal },
  { value: "pct_row", label: tp.showPctRow },
  { value: "pct_column", label: tp.showPctColumn },
];
const DATE_GROUPS: { value: PivotField["date_group"]; label: string }[] = [
  { value: "none", label: tp.none },
  { value: "year", label: tp.year },
  { value: "quarter", label: tp.quarter },
  { value: "month", label: tp.month },
  { value: "day", label: tp.day },
];

interface DragData {
  column: string;
  from?: Zone;
  index?: number;
}

/** Add a field to a zone (Excel defaults: numbers are summed, anything else is counted). */
export function addToZone(
  cfg: PivotConfig,
  zone: Zone,
  column: string,
  type: Column["type"] | undefined,
): PivotConfig {
  const isDate = type === "date" || type === "datetime";
  switch (zone) {
    case "rows":
      return cfg.rows.some((r) => r.column === column)
        ? cfg
        : { ...cfg, rows: [...cfg.rows, { column, date_group: isDate ? "month" : "none" }] };
    case "columns":
      return { ...cfg, columns: { column, date_group: isDate ? "year" : "none" }, column_values: [] };
    case "values": {
      const numeric = type === "integer" || type === "decimal";
      return {
        ...cfg,
        values: [
          ...cfg.values,
          { column, fn: numeric ? "sum" : "count_non_null", show_as: "normal", label: null },
        ],
      };
    }
    case "filters":
      return cfg.filters.some((f) => f.column === column)
        ? cfg
        : { ...cfg, filters: [...cfg.filters, newCondition(column, "in")] };
  }
}

export function removeFromZone(cfg: PivotConfig, zone: Zone, index: number): PivotConfig {
  switch (zone) {
    case "rows":
      return { ...cfg, rows: cfg.rows.filter((_, i) => i !== index) };
    case "columns":
      return { ...cfg, columns: null, column_values: [] };
    case "values":
      return { ...cfg, values: cfg.values.filter((_, i) => i !== index) };
    case "filters":
      return { ...cfg, filters: cfg.filters.filter((_, i) => i !== index) };
  }
}

function FieldChip({ c, onAdd }: { c: Column; onAdd: (zone: Zone) => void }) {
  const { attributes, listeners, setNodeRef, isDragging } = useDraggable({
    id: `field:${c.name}`,
    data: { column: c.name } satisfies DragData,
  });
  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <button
          ref={setNodeRef}
          type="button"
          {...listeners}
          {...attributes}
          className={cn(
            "flex max-w-full cursor-grab items-center gap-1 rounded border bg-card px-1.5 py-0.5 text-xs hover:border-primary",
            isDragging && "opacity-40",
          )}
        >
          <TypeIcon type={c.type} />
          <span className="truncate">{c.name}</span>
        </button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="start">
        <DropdownMenuLabel>Adicionar a…</DropdownMenuLabel>
        {ZONES.map((z) => (
          <DropdownMenuItem key={z} onSelect={() => onAdd(z)}>
            {tp[z]}
          </DropdownMenuItem>
        ))}
      </DropdownMenuContent>
    </DropdownMenu>
  );
}

function ZoneBox({ zone, children, empty }: { zone: Zone; children: ReactNode; empty: boolean }) {
  const { setNodeRef, isOver } = useDroppable({ id: zone });
  return (
    <div
      ref={setNodeRef}
      className={cn(
        "flex min-h-14 flex-col gap-1 rounded-md border border-dashed p-1.5 transition-colors",
        isOver && "border-primary bg-primary/5",
      )}
      data-testid={`pivot-zone-${zone}`}
    >
      <span className="text-[10px] font-semibold uppercase tracking-wide text-muted-foreground">
        {tp[zone]}
      </span>
      {empty ? <span className="px-1 text-[11px] text-muted-foreground">{tp.dropHere}</span> : children}
    </div>
  );
}

function ZoneItem({
  zone,
  index,
  column,
  onRemove,
  children,
}: {
  zone: Zone;
  index: number;
  column: string;
  onRemove: () => void;
  children?: ReactNode;
}) {
  const { attributes, listeners, setNodeRef } = useDraggable({
    id: `${zone}:${index}`,
    data: { column, from: zone, index } satisfies DragData,
  });
  return (
    <div className="flex flex-col gap-1 rounded border bg-card p-1.5">
      <div className="flex items-center gap-1">
        <span
          ref={setNodeRef}
          {...listeners}
          {...attributes}
          className="cursor-grab text-muted-foreground"
          aria-label="Mover"
        >
          <GripVertical className="size-3.5" />
        </span>
        <span className="min-w-0 flex-1 truncate text-xs font-medium">{column}</span>
        <button
          type="button"
          onClick={onRemove}
          className="cursor-pointer text-muted-foreground hover:text-foreground"
          aria-label={`${t.common.remove} ${column}`}
        >
          <X className="size-3.5" />
        </button>
      </div>
      {children}
    </div>
  );
}

function ColumnValues({
  node,
  config,
  update,
}: Pick<ConfigPanelProps<PivotConfig>, "node" | "config" | "update">) {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const field = config.columns;
  const refresh = async () => {
    if (!field) return;
    setLoading(true);
    setError(null);
    try {
      const res = await fetchPivotValues(
        usePipelineStore.getState().pipeline,
        node.id,
        field.column,
        field.date_group,
      );
      if (res.truncated || res.values.length > MAX_VALUES) {
        setError(tp.tooMany);
        return;
      }
      update((c) => ({ ...c, column_values: res.values.map(String) }));
    } catch (e) {
      setError(e instanceof ApiError ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  };
  // Resolve the generated columns as soon as a field lands in "Colunas".
  const key = field ? `${field.column}|${field.date_group}` : "";
  const last = useRef(key);
  useEffect(() => {
    if (key && (last.current !== key || config.column_values.length === 0)) void refresh();
    last.current = key;
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key]);
  if (!field) return null;
  return (
    <div className="flex items-center gap-2 text-[11px] text-muted-foreground">
      {loading ? <Spinner className="size-3" /> : <span>{tp.columnValues(config.column_values.length)}</span>}
      <Button variant="ghost" size="sm" onClick={() => void refresh()} disabled={loading}>
        <RefreshCw /> {tp.refresh}
      </Button>
      {error && <span className="text-danger">{error}</span>}
    </div>
  );
}

export function ConfigPanel({ node, config, update, columns }: ConfigPanelProps<PivotConfig>) {
  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 4 } }),
    useSensor(KeyboardSensor),
  );
  const typeOf = (name: string) => columns.find((c) => c.name === name)?.type;
  const isDate = (name: string) => ["date", "datetime"].includes(typeOf(name) ?? "");

  const onDragEnd = (e: DragEndEvent) => {
    const data = e.active.data.current as DragData | undefined;
    const zone = e.over?.id as Zone | undefined;
    if (!data) return;
    update((c) => {
      let next = c;
      if (data.from !== undefined && data.index !== undefined) {
        if (data.from === zone) return c;
        next = removeFromZone(next, data.from, data.index);
      }
      return zone ? addToZone(next, zone, data.column, typeOf(data.column)) : next;
    });
  };

  const setValue = (i: number, patch: Partial<PivotValue>) =>
    update({ ...config, values: config.values.map((v, j) => (j === i ? { ...v, ...patch } : v)) });
  const setFilter = (i: number, patch: Partial<Condition>) =>
    update({ ...config, filters: config.filters.map((f, j) => (j === i ? { ...f, ...patch } : f)) });

  return (
    <DndContext sensors={sensors} onDragEnd={onDragEnd}>
      <div className="flex flex-col gap-3">
        <div className="flex flex-col gap-1">
          <span className="text-xs font-medium text-muted-foreground">{tp.fields}</span>
          <div className="flex max-h-32 flex-wrap gap-1 overflow-auto">
            {columns.map((c) => (
              <FieldChip
                key={c.name}
                c={c}
                onAdd={(z) => update((cfg) => addToZone(cfg, z, c.name, c.type))}
              />
            ))}
          </div>
        </div>

        <ZoneBox zone="filters" empty={!config.filters.length}>
          {config.filters.map((f, i) => (
            <ZoneItem
              key={f.column}
              zone="filters"
              index={i}
              column={f.column}
              onRemove={() => update(removeFromZone(config, "filters", i))}
            >
              <Input
                className="h-7"
                placeholder={tp.filterValues}
                defaultValue={f.values.map(String).join("; ")}
                onBlur={(e) =>
                  setFilter(i, {
                    operator: "in",
                    values: e.target.value
                      .split(";")
                      .map((v) => v.trim())
                      .filter(Boolean),
                  })
                }
              />
            </ZoneItem>
          ))}
        </ZoneBox>

        <ZoneBox zone="columns" empty={!config.columns}>
          {config.columns && (
            <ZoneItem
              zone="columns"
              index={0}
              column={config.columns.column}
              onRemove={() => update(removeFromZone(config, "columns", 0))}
            >
              {isDate(config.columns.column) && (
                <Select
                  value={config.columns.date_group}
                  options={DATE_GROUPS}
                  onChange={(date_group) =>
                    config.columns &&
                    update({ ...config, columns: { ...config.columns, date_group }, column_values: [] })
                  }
                  aria-label={tp.groupDate}
                />
              )}
              <ColumnValues node={node} config={config} update={update} />
            </ZoneItem>
          )}
        </ZoneBox>

        <ZoneBox zone="rows" empty={!config.rows.length}>
          {config.rows.map((r, i) => (
            <ZoneItem
              key={r.column}
              zone="rows"
              index={i}
              column={r.column}
              onRemove={() => update(removeFromZone(config, "rows", i))}
            >
              {isDate(r.column) && (
                <Select
                  value={r.date_group}
                  options={DATE_GROUPS}
                  onChange={(date_group) =>
                    update({
                      ...config,
                      rows: config.rows.map((x, j) => (j === i ? { ...x, date_group } : x)),
                    })
                  }
                  aria-label={tp.groupDate}
                />
              )}
            </ZoneItem>
          ))}
        </ZoneBox>

        <ZoneBox zone="values" empty={!config.values.length}>
          {config.values.map((v, i) => (
            <ZoneItem
              key={i}
              zone="values"
              index={i}
              column={v.column ?? "*"}
              onRemove={() => update(removeFromZone(config, "values", i))}
            >
              <Select
                value={v.fn}
                options={AGG_FNS}
                onChange={(fn) => setValue(i, { fn })}
                aria-label="Agregação"
              />
              <Select
                value={v.show_as}
                options={SHOW_AS}
                onChange={(show_as) => setValue(i, { show_as })}
                aria-label={tp.showAs}
              />
              <Input
                className="h-7"
                placeholder={tp.label}
                value={v.label ?? ""}
                onChange={(e) => setValue(i, { label: e.target.value || null })}
                aria-label={tp.label}
              />
            </ZoneItem>
          ))}
        </ZoneBox>

        <Switch
          checked={config.totals}
          onCheckedChange={(totals) => update({ ...config, totals })}
          label={tp.totals}
        />
        {config.columns && config.values.length > 1 && (
          <Field label={tp.template}>
            <Input
              value={config.name_template}
              onChange={(e) => update({ ...config, name_template: e.target.value })}
            />
          </Field>
        )}
      </div>
    </DndContext>
  );
}
