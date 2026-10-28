import type { LookupConfig, LookupKey } from "@/api/types";
import { Field, Input, Select } from "@/components/ui";
import { useInputColumns } from "@/features/editor/analysis";
import { t } from "@/i18n/pt-BR";

import { KeyPairs } from "../join/ConfigPanel";
import { ColumnMultiSelect } from "../shared/ColumnSelect";
import type { ConfigPanelProps } from "../shared/panel";

const tt = t.nodes2;

export function ConfigPanel({ node, config, update }: ConfigPanelProps<LookupConfig>) {
  const lookupColumns = useInputColumns(node.id, "lookup");
  const keyNames = new Set(config.keys.map((k) => k.lookup));
  return (
    <div className="flex flex-col gap-3">
      <KeyPairs<LookupKey>
        value={config.keys}
        onChange={(keys) => update({ ...config, keys })}
        left={{ handle: "main", field: "main", nodeId: node.id }}
        right={{ handle: "lookup", field: "lookup", nodeId: node.id }}
        labels={[tt.mainKey, tt.lookupKey]}
      />
      <Field label={tt.bring}>
        <ColumnMultiSelect
          columns={lookupColumns.filter((c) => !keyNames.has(c.name))}
          value={config.columns}
          onChange={(columns) => update({ ...config, columns })}
        />
      </Field>
      <Field label={tt.prefix}>
        <Input value={config.prefix} onChange={(e) => update({ ...config, prefix: e.target.value })} />
      </Field>
      <Field label={tt.onMultiple}>
        <Select
          value={config.on_multiple}
          options={[
            { value: "first", label: tt.onMultipleFirst },
            { value: "error", label: tt.onMultipleError },
          ]}
          onChange={(on_multiple) => update({ ...config, on_multiple })}
        />
      </Field>
    </div>
  );
}
