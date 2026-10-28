import { Plus, Trash2 } from "lucide-react";

import type { Column, ConditionalConfig, Outcome } from "@/api/types";
import { Button, Field, Input, Select } from "@/components/ui";
import { t } from "@/i18n/pt-BR";

import { GroupEditor, newCondition } from "../filter/ConfigPanel";
import { ColumnSelect } from "../shared/ColumnSelect";
import type { ConfigPanelProps } from "../shared/panel";

const tt = t.nodes2;

function OutcomeEditor({
  value,
  onChange,
  columns,
}: {
  value: Outcome;
  onChange: (o: Outcome) => void;
  columns: Column[];
}) {
  return (
    <div className="flex items-center gap-1.5">
      <Select
        className="w-24 shrink-0"
        value={value.kind}
        options={[
          { value: "value", label: tt.fixedValue },
          { value: "column", label: tt.fromColumn },
        ]}
        onChange={(kind) => onChange({ ...value, kind })}
      />
      {value.kind === "value" ? (
        <Input
          className="h-8"
          value={value.value == null ? "" : String(value.value)}
          onChange={(e) => onChange({ ...value, value: e.target.value })}
          placeholder={t.common.value}
          aria-label={t.common.value}
        />
      ) : (
        <ColumnSelect
          columns={columns}
          value={value.column}
          onChange={(column) => onChange({ ...value, column })}
        />
      )}
    </div>
  );
}

export function ConfigPanel({ node, config, update, columns }: ConfigPanelProps<ConditionalConfig>) {
  const setRule = (i: number, patch: Partial<ConditionalConfig["rules"][number]>) =>
    update({ ...config, rules: config.rules.map((r, j) => (j === i ? { ...r, ...patch } : r)) });
  return (
    <div className="flex flex-col gap-3">
      <div className="grid grid-cols-[auto_1fr] gap-2">
        <Field label={t.nodes.calculated.mode}>
          <Select
            value={config.mode}
            options={[
              { value: "new", label: t.nodes.calculated.modeNew },
              { value: "replace", label: t.nodes.calculated.modeReplace },
            ]}
            onChange={(mode) => update({ ...config, mode })}
          />
        </Field>
        <Field label={t.nodes.calculated.name}>
          {config.mode === "new" ? (
            <Input value={config.name} onChange={(e) => update({ ...config, name: e.target.value })} />
          ) : (
            <ColumnSelect
              columns={columns}
              value={config.name}
              onChange={(name) => update({ ...config, name })}
            />
          )}
        </Field>
      </div>
      {config.rules.map((r, i) => (
        <div key={i} className="flex flex-col gap-2 rounded-md border p-2">
          <div className="flex items-center justify-between">
            <span className="text-xs font-bold text-cat-columns">
              {i === 0 ? tt.when : `SENÃO ${tt.when}`}
            </span>
            <Button
              variant="ghost"
              size="iconSm"
              aria-label={t.common.remove}
              onClick={() => update({ ...config, rules: config.rules.filter((_, j) => j !== i) })}
            >
              <Trash2 />
            </Button>
          </div>
          <GroupEditor
            group={r.when}
            columns={columns}
            nodeId={node.id}
            onChange={(when) => setRule(i, { when })}
          />
          <span className="text-xs font-bold text-cat-columns">{tt.then}</span>
          <OutcomeEditor value={r.then} onChange={(then) => setRule(i, { then })} columns={columns} />
        </div>
      ))}
      <Button
        variant="outline"
        size="sm"
        className="self-start"
        onClick={() =>
          update({
            ...config,
            rules: [
              ...config.rules,
              {
                when: { kind: "group", op: "and", conditions: [newCondition(columns[0]?.name ?? "")] },
                then: { kind: "value", value: "", column: null },
              },
            ],
          })
        }
      >
        <Plus /> {tt.addIf}
      </Button>
      <div className="flex flex-col gap-1">
        <span className="text-xs font-bold text-cat-columns">{tt.otherwise}</span>
        <OutcomeEditor
          value={config.otherwise}
          onChange={(otherwise) => update({ ...config, otherwise })}
          columns={columns}
        />
      </div>
    </div>
  );
}
