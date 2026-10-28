import { FolderPlus, Plus, Trash2 } from "lucide-react";
import { useId } from "react";

import { useDistinctValues } from "@/api/hooks";
import type { Column, Condition, ConditionGroup, FilterConfig, LogicalType } from "@/api/types";
import { Button, Checkbox, Field, Input, Select } from "@/components/ui";
import { useServerPipeline } from "@/features/editor/analysis";
import { FormulaEditor } from "@/features/formula/FormulaEditor";
import { t } from "@/i18n/pt-BR";
import { cn } from "@/lib/utils";
import { usePipelineStore } from "@/stores/pipelineStore";

import { ColumnSelect } from "../shared/ColumnSelect";
import type { ConfigPanelProps } from "../shared/panel";

type Op = Condition["operator"];
type Item = Condition | ConditionGroup;

const BY_TYPE: Record<string, Op[]> = {
  text: [
    "eq",
    "neq",
    "contains",
    "not_contains",
    "starts_with",
    "ends_with",
    "in",
    "not_in",
    "is_null",
    "is_not_null",
  ],
  number: ["eq", "neq", "gt", "gte", "lt", "lte", "between", "in", "not_in", "is_null", "is_not_null"],
  date: ["eq", "neq", "gt", "gte", "lt", "lte", "between", "is_null", "is_not_null"],
  boolean: ["is_true", "is_false", "is_null", "is_not_null"],
};

function opsFor(type: LogicalType | undefined): Op[] {
  if (type === "integer" || type === "decimal") return BY_TYPE.number ?? [];
  if (type === "date" || type === "datetime" || type === "time") return BY_TYPE.date ?? [];
  if (type === "boolean") return BY_TYPE.boolean ?? [];
  return BY_TYPE.text ?? [];
}

const NO_VALUE: Op[] = ["is_null", "is_not_null", "is_true", "is_false"];

export function newCondition(
  column: string,
  operator: Op = "eq",
  value: Condition["value"] = null,
): Condition {
  return { kind: "condition", column, operator, value, value2: null, values: [], case_sensitive: false };
}

function ValueInput({
  nodeId,
  column,
  value,
  onChange,
  type,
}: {
  nodeId: string;
  column: string;
  value: Condition["value"];
  onChange: (v: string) => void;
  type: LogicalType | undefined;
}) {
  const listId = useId();
  const pipeline = useServerPipeline((s) => s.pipeline);
  const { data } = useDistinctValues(pipeline, nodeId, type === "text" ? column : null);
  const placeholder =
    type === "date"
      ? "dd/mm/aaaa"
      : type === "datetime"
        ? "dd/mm/aaaa hh:mm"
        : t.nodes.filter.valuePlaceholder;
  return (
    <>
      <Input
        className="h-7"
        value={value == null ? "" : String(value)}
        placeholder={placeholder}
        list={listId}
        onChange={(e) => onChange(e.target.value)}
        aria-label={t.common.value}
      />
      <datalist id={listId}>
        {data?.values.slice(0, 100).map((v) => (
          <option key={String(v)} value={String(v)} />
        ))}
      </datalist>
    </>
  );
}

function ConditionRow({
  c,
  columns,
  nodeId,
  onChange,
  onRemove,
}: {
  c: Condition;
  columns: Column[];
  nodeId: string;
  onChange: (c: Condition) => void;
  onRemove: () => void;
}) {
  const type = columns.find((x) => x.name === c.column)?.type;
  const ops = opsFor(type);
  return (
    <div className="flex flex-col gap-1.5 rounded-md border bg-card p-2">
      <div className="flex items-center gap-1.5">
        <ColumnSelect
          columns={columns}
          value={c.column}
          onChange={(column) => {
            const nt = columns.find((x) => x.name === column)?.type;
            const nextOps = opsFor(nt);
            onChange({
              ...c,
              column,
              operator: nextOps.includes(c.operator) ? c.operator : (nextOps[0] ?? "eq"),
            });
          }}
          className="h-7"
        />
        <Button variant="ghost" size="iconSm" onClick={onRemove} aria-label={t.common.remove}>
          <Trash2 />
        </Button>
      </div>
      <Select
        value={c.operator}
        options={ops.map((o) => ({ value: o, label: t.operators[o] ?? o }))}
        onChange={(operator) => onChange({ ...c, operator })}
      />
      {!NO_VALUE.includes(c.operator) &&
        (c.operator === "in" || c.operator === "not_in" ? (
          <Input
            className="h-7"
            placeholder={t.nodes.filter.valuesPlaceholder}
            defaultValue={c.values.map(String).join("; ")}
            onBlur={(e) =>
              onChange({
                ...c,
                values: e.target.value
                  .split(";")
                  .map((v) => v.trim())
                  .filter(Boolean),
              })
            }
          />
        ) : (
          <div className="flex items-center gap-1.5">
            <ValueInput
              nodeId={nodeId}
              column={c.column}
              type={type}
              value={c.value}
              onChange={(v) => onChange({ ...c, value: v })}
            />
            {c.operator === "between" && (
              <>
                <span className="text-xs text-muted-foreground">e</span>
                <Input
                  className="h-7"
                  value={c.value2 == null ? "" : String(c.value2)}
                  onChange={(e) => onChange({ ...c, value2: e.target.value })}
                  aria-label="Valor final"
                />
              </>
            )}
          </div>
        ))}
      {type === "text" && !NO_VALUE.includes(c.operator) && (
        <Checkbox
          checked={c.case_sensitive}
          onCheckedChange={(v) => onChange({ ...c, case_sensitive: v })}
          label={<span className="text-xs text-muted-foreground">{t.nodes.filter.caseSensitive}</span>}
        />
      )}
    </div>
  );
}

export function GroupEditor({
  group,
  columns,
  nodeId,
  onChange,
  onRemove,
  depth = 0,
}: {
  group: ConditionGroup;
  columns: Column[];
  nodeId: string;
  onChange: (g: ConditionGroup) => void;
  onRemove?: () => void;
  depth?: number;
}) {
  const tt = t.nodes.filter;
  const setItem = (i: number, item: Item) =>
    onChange({ ...group, conditions: group.conditions.map((x, j) => (j === i ? item : x)) });
  const removeItem = (i: number) =>
    onChange({ ...group, conditions: group.conditions.filter((_, j) => j !== i) });
  const first = columns[0]?.name ?? "";
  return (
    <div
      className={cn("flex flex-col gap-2", depth > 0 && "rounded-md border border-dashed bg-muted/50 p-2")}
    >
      <div className="flex items-center gap-2">
        <Select
          className="flex-1"
          value={group.op}
          options={[
            { value: "and", label: tt.matchAll },
            { value: "or", label: tt.matchAny },
          ]}
          onChange={(op) => onChange({ ...group, op })}
        />
        {onRemove && (
          <Button variant="ghost" size="iconSm" onClick={onRemove} aria-label={t.common.remove}>
            <Trash2 />
          </Button>
        )}
      </div>
      {group.conditions.map((item, i) => (
        <div key={i} className="flex flex-col gap-1">
          {i > 0 && (
            <span className="self-center text-[10px] font-bold text-muted-foreground">
              {group.op === "and" ? tt.and : tt.or}
            </span>
          )}
          {item.kind === "group" ? (
            <GroupEditor
              group={item}
              columns={columns}
              nodeId={nodeId}
              onChange={(g) => setItem(i, g)}
              onRemove={() => removeItem(i)}
              depth={depth + 1}
            />
          ) : (
            <ConditionRow
              c={item}
              columns={columns}
              nodeId={nodeId}
              onChange={(c) => setItem(i, c)}
              onRemove={() => removeItem(i)}
            />
          )}
        </div>
      ))}
      <div className="flex gap-2">
        <Button
          variant="outline"
          size="sm"
          onClick={() => onChange({ ...group, conditions: [...group.conditions, newCondition(first)] })}
        >
          <Plus /> {tt.addCondition}
        </Button>
        {depth < 2 && (
          <Button
            variant="ghost"
            size="sm"
            onClick={() =>
              onChange({
                ...group,
                conditions: [
                  ...group.conditions,
                  { kind: "group", op: group.op === "and" ? "or" : "and", conditions: [newCondition(first)] },
                ],
              })
            }
          >
            <FolderPlus /> {tt.addGroup}
          </Button>
        )}
      </div>
    </div>
  );
}

export function ConfigPanel({ node, config, update, columns }: ConfigPanelProps<FilterConfig>) {
  const tt = t.nodes.filter;
  const locale = usePipelineStore((s) => s.pipeline.settings.locale);
  return (
    <div className="flex flex-col gap-3">
      <Field label="Modo">
        <Select
          value={config.mode}
          options={[
            { value: "rules", label: tt.rules },
            { value: "formula", label: tt.formula },
          ]}
          onChange={(mode) => update({ ...config, mode })}
        />
      </Field>
      {config.mode === "rules" ? (
        <GroupEditor
          group={config.rules}
          columns={columns}
          nodeId={node.id}
          onChange={(rules) => update({ ...config, rules })}
        />
      ) : (
        <FormulaEditor
          value={config.formula}
          onChange={(formula) => update((c) => ({ ...c, formula }))}
          columns={columns}
          locale={locale}
          nodeId={node.id}
          placeholder='Ex.: E([uf] = "PR"; [valor] > 100)'
        />
      )}
    </div>
  );
}
