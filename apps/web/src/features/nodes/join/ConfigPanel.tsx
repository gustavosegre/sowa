import { Plus, Trash2 } from "lucide-react";

import type { JoinConfig, JoinKey } from "@/api/types";
import { Button, Field, Input, Select } from "@/components/ui";
import { useInputColumns } from "@/features/editor/analysis";
import { t } from "@/i18n/pt-BR";

import { ColumnSelect } from "../shared/ColumnSelect";
import type { ConfigPanelProps } from "../shared/panel";

const tt = t.nodes2;

/** Key pairs between two inputs; shared with Procurar (PROCV). */
export function KeyPairs<K extends Record<string, string>>({
  value,
  onChange,
  left,
  right,
  labels,
}: {
  value: K[];
  onChange: (v: K[]) => void;
  left: { handle: string; field: keyof K & string; nodeId: string };
  right: { handle: string; field: keyof K & string; nodeId: string };
  labels: [string, string];
}) {
  const lc = useInputColumns(left.nodeId, left.handle);
  const rc = useInputColumns(right.nodeId, right.handle);
  if (!lc.length || !rc.length) return <p className="text-xs text-muted-foreground">{tt.connectBoth}</p>;
  const set = (i: number, patch: Partial<K>) =>
    onChange(value.map((k, j) => (j === i ? { ...k, ...patch } : k)));
  return (
    <div className="flex flex-col gap-1.5">
      <div className="grid grid-cols-[1fr_1fr_auto] gap-1.5 text-xs font-medium text-muted-foreground">
        <span>{labels[0]}</span>
        <span>{labels[1]}</span>
        <span className="w-6" />
      </div>
      {value.map((k, i) => (
        <div key={i} className="grid grid-cols-[1fr_1fr_auto] gap-1.5">
          <ColumnSelect
            columns={lc}
            value={k[left.field]}
            onChange={(v) => set(i, { [left.field]: v } as Partial<K>)}
          />
          <ColumnSelect
            columns={rc}
            value={k[right.field]}
            onChange={(v) => set(i, { [right.field]: v } as Partial<K>)}
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
        variant="outline"
        size="sm"
        className="self-start"
        onClick={() => {
          // Suggest a column present on both sides with the same name.
          const same = lc.find((c) => rc.some((r) => r.name === c.name));
          const l = same?.name ?? lc[0]?.name ?? "";
          const r = same?.name ?? rc[0]?.name ?? "";
          onChange([...value, { [left.field]: l, [right.field]: r } as K]);
        }}
      >
        <Plus /> {tt.addKey}
      </Button>
    </div>
  );
}

export function ConfigPanel({ node, config, update }: ConfigPanelProps<JoinConfig>) {
  return (
    <div className="flex flex-col gap-3">
      <Field label={tt.joinHow}>
        <Select
          value={config.how}
          options={Object.entries(tt.joinKinds).map(([value, label]) => ({
            value: value as JoinConfig["how"],
            label,
          }))}
          onChange={(how) => update({ ...config, how })}
        />
      </Field>
      <KeyPairs<JoinKey>
        value={config.keys}
        onChange={(keys) => update({ ...config, keys })}
        left={{ handle: "left", field: "left", nodeId: node.id }}
        right={{ handle: "right", field: "right", nodeId: node.id }}
        labels={[tt.leftKey, tt.rightKey]}
      />
      <Field label={tt.suffix}>
        <Input value={config.suffix} onChange={(e) => update({ ...config, suffix: e.target.value })} />
      </Field>
    </div>
  );
}
