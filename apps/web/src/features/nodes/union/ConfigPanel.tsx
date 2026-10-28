import type { UnionConfig } from "@/api/types";
import { Field, Input, Select } from "@/components/ui";
import { t } from "@/i18n/pt-BR";

import type { ConfigPanelProps } from "../shared/panel";

const tt = t.nodes2;

export function ConfigPanel({ config, update }: ConfigPanelProps<UnionConfig>) {
  return (
    <div className="flex flex-col gap-3">
      <p className="text-[11px] text-muted-foreground">{tt.unionHint}</p>
      <Field label={tt.mode}>
        <Select
          value={config.mode}
          options={[
            { value: "by_name", label: tt.unionByName },
            { value: "by_position", label: tt.unionByPosition },
          ]}
          onChange={(mode) => update({ ...config, mode })}
        />
      </Field>
      <Field label={tt.sourceColumn}>
        <Input
          value={config.source_column ?? ""}
          placeholder="origem"
          onChange={(e) =>
            update({ ...config, source_column: e.target.value.trim() ? e.target.value : null })
          }
        />
      </Field>
    </div>
  );
}
