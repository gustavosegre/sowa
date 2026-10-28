import type { CalculatedConfig } from "@/api/types";
import { Field, Input, Select } from "@/components/ui";
import { FormulaEditor } from "@/features/formula/FormulaEditor";
import { FunctionHelp } from "@/features/formula/FunctionHelp";
import { t } from "@/i18n/pt-BR";
import { usePipelineStore } from "@/stores/pipelineStore";

import { ColumnSelect } from "../shared/ColumnSelect";
import type { ConfigPanelProps } from "../shared/panel";

export function ConfigPanel({ node, config, update, columns }: ConfigPanelProps<CalculatedConfig>) {
  const tt = t.nodes.calculated;
  const locale = usePipelineStore((s) => s.pipeline.settings.locale);
  return (
    <div className="flex flex-col gap-3">
      <Field label={tt.mode}>
        <Select
          value={config.mode}
          options={[
            { value: "new", label: tt.modeNew },
            { value: "replace", label: tt.modeReplace },
          ]}
          onChange={(mode) => update({ ...config, mode })}
        />
      </Field>
      <Field label={tt.name}>
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
      <Field label={tt.formula}>
        <FormulaEditor
          value={config.formula}
          onChange={(formula) => update((c) => ({ ...c, formula }))}
          columns={columns}
          locale={locale}
          nodeId={node.id}
          ariaLabel={tt.formula}
        />
      </Field>
      <FunctionHelp context="row" />
    </div>
  );
}
