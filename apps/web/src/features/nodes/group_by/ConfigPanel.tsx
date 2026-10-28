import { Plus, Trash2 } from "lucide-react";

import type { Aggregation, GroupByConfig, Measure } from "@/api/types";
import { Button, Field, Input, SectionTitle, Select } from "@/components/ui";
import { FormulaEditor } from "@/features/formula/FormulaEditor";
import { FunctionHelp } from "@/features/formula/FunctionHelp";
import { t } from "@/i18n/pt-BR";
import { usePipelineStore } from "@/stores/pipelineStore";

import { ColumnMultiSelect, ColumnSelect } from "../shared/ColumnSelect";
import type { ConfigPanelProps } from "../shared/panel";

const AGG_FNS = Object.entries(t.aggs).map(([value, label]) => ({
  value: value as Aggregation["fn"],
  label,
}));
const NUMERIC_ONLY = new Set(["sum", "avg", "median", "stddev", "variance", "percentile"]);

export function newAgg(column: string | null, fn: Aggregation["fn"] = "sum"): Aggregation {
  return { column, fn, as: "", percentile: 0.5, separator: ", ", order_by: null };
}

export function ConfigPanel({ node, config, update, columns }: ConfigPanelProps<GroupByConfig>) {
  const tt = t.nodes.groupBy;
  const locale = usePipelineStore((s) => s.pipeline.settings.locale);
  const setAgg = (i: number, patch: Partial<Aggregation>) =>
    update({ ...config, aggs: config.aggs.map((a, j) => (j === i ? { ...a, ...patch } : a)) });
  const setMeasure = (i: number, patch: Partial<Measure>) =>
    update((c) => ({ ...c, measures: c.measures.map((m, j) => (j === i ? { ...m, ...patch } : m)) }));
  const numeric = columns.filter((c) => c.type === "integer" || c.type === "decimal");

  return (
    <div className="flex flex-col gap-4">
      <Field label={tt.keys}>
        <ColumnMultiSelect
          columns={columns}
          value={config.keys}
          onChange={(keys) => update({ ...config, keys })}
        />
      </Field>

      <div className="flex flex-col gap-2">
        <SectionTitle>{tt.aggs}</SectionTitle>
        {config.aggs.map((a, i) => (
          <div key={i} className="flex flex-col gap-1.5 rounded-md border p-2">
            <div className="flex items-center gap-1.5">
              <Select
                value={a.fn}
                options={AGG_FNS}
                onChange={(fn) =>
                  setAgg(i, { fn, column: fn === "count" ? null : (a.column ?? numeric[0]?.name ?? null) })
                }
              />
              <Button
                variant="ghost"
                size="iconSm"
                aria-label={t.common.remove}
                onClick={() => update({ ...config, aggs: config.aggs.filter((_, j) => j !== i) })}
              >
                <Trash2 />
              </Button>
            </div>
            {a.fn !== "count" && (
              <ColumnSelect
                columns={NUMERIC_ONLY.has(a.fn) ? numeric : columns}
                value={a.column}
                onChange={(column) => setAgg(i, { column })}
              />
            )}
            {a.fn === "percentile" && (
              <Field label={tt.percentile}>
                <Input
                  type="number"
                  step="0.05"
                  min={0}
                  max={1}
                  value={a.percentile}
                  onChange={(e) => setAgg(i, { percentile: Number(e.target.value) })}
                />
              </Field>
            )}
            {(a.fn === "first" || a.fn === "last" || a.fn === "concat") && (
              <Field label={tt.orderBy}>
                <ColumnSelect
                  columns={columns}
                  value={a.order_by}
                  allowEmpty
                  onChange={(o) => setAgg(i, { order_by: o || null })}
                />
              </Field>
            )}
            {a.fn === "concat" && (
              <Field label={tt.separator}>
                <Input value={a.separator} onChange={(e) => setAgg(i, { separator: e.target.value })} />
              </Field>
            )}
            <Input
              className="h-7"
              placeholder={a.fn === "count" ? "contagem" : `${a.fn}_${a.column ?? ""}`}
              value={a.as}
              onChange={(e) => setAgg(i, { as: e.target.value })}
              aria-label={tt.as}
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
              aggs: [...config.aggs, newAgg(numeric[0]?.name ?? null, numeric[0] ? "sum" : "count")],
            })
          }
        >
          <Plus /> {tt.addAgg}
        </Button>
      </div>

      <div className="flex flex-col gap-2">
        <SectionTitle>{tt.measures}</SectionTitle>
        <p className="text-[11px] text-muted-foreground">{tt.measureHint}</p>
        {config.measures.map((m, i) => (
          <div key={i} className="flex flex-col gap-1.5 rounded-md border p-2">
            <div className="flex items-center gap-1.5">
              <Input
                value={m.name}
                onChange={(e) => setMeasure(i, { name: e.target.value })}
                aria-label={tt.as}
              />
              <Button
                variant="ghost"
                size="iconSm"
                aria-label={t.common.remove}
                onClick={() => update({ ...config, measures: config.measures.filter((_, j) => j !== i) })}
              >
                <Trash2 />
              </Button>
            </div>
            <FormulaEditor
              value={m.formula}
              onChange={(formula) => setMeasure(i, { formula })}
              columns={columns}
              locale={locale}
              context="aggregate"
              groupKeys={config.keys}
              nodeId={node.id}
              placeholder="SOMA([receita]) / SOMA([quantidade])"
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
              measures: [...config.measures, { name: `medida_${config.measures.length + 1}`, formula: "" }],
            })
          }
        >
          <Plus /> {tt.addMeasure}
        </Button>
        {config.measures.length > 0 && <FunctionHelp context="aggregate" />}
      </div>
    </div>
  );
}
