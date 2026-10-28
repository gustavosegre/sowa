import { FileUp, RefreshCw } from "lucide-react";

import { useSources } from "@/api/hooks";
import type { SourceConfig } from "@/api/types";
import { Button, Field, Input, Select, Switch } from "@/components/ui";
import { useProjectId } from "@/features/editor/project";
import { t } from "@/i18n/pt-BR";
import { fmtBytes, fmtInt } from "@/lib/utils";
import { useUiStore } from "@/stores/uiStore";

import type { ConfigPanelProps } from "../shared/panel";

export function ConfigPanel({ config, update }: ConfigPanelProps<SourceConfig>) {
  const projectId = useProjectId();
  const { data: sources = [] } = useSources(projectId);
  const openWizard = useUiStore((s) => s.openWizard);
  const current = sources.find((s) => s.id === config.source_id);
  const ready = sources.filter((s) => s.status === "ready");
  const tt = t.nodes.source;

  return (
    <div className="flex flex-col gap-3">
      <Field label={tt.file}>
        <Select
          value={config.source_id}
          placeholder={tt.pick}
          options={ready.map((s) => ({ value: s.id, label: s.name }))}
          onChange={(v) => update({ ...config, source_id: v })}
        />
      </Field>
      {current && (
        <p className="text-[11px] text-muted-foreground">
          {current.filename} · {fmtBytes(current.size_bytes)} · {fmtInt(current.row_count)} linhas ·{" "}
          {current.columns?.length ?? 0} colunas
        </p>
      )}
      <div className="flex gap-2">
        <Button variant="outline" size="sm" onClick={() => openWizard()}>
          <FileUp /> {t.editor.upload}
        </Button>
        {current && (
          <Button variant="outline" size="sm" onClick={() => openWizard({ replaceSourceId: current.id })}>
            <RefreshCw /> {tt.replace}
          </Button>
        )}
      </div>
      <div className="flex flex-col gap-2 border-t pt-3">
        <Switch
          checked={config.sample != null}
          onCheckedChange={(on) =>
            update({ ...config, sample: on ? { mode: "first", rows: 10000, seed: 42 } : null })
          }
          label={tt.sample}
        />
        {config.sample && (
          <div className="grid grid-cols-2 gap-2">
            <Field label={t.common.type}>
              <Select
                value={config.sample.mode}
                options={[
                  { value: "first", label: tt.sampleFirst },
                  { value: "random", label: tt.sampleRandom },
                ]}
                onChange={(mode) =>
                  config.sample && update({ ...config, sample: { ...config.sample, mode } })
                }
              />
            </Field>
            <Field label={tt.sampleRows}>
              <Input
                type="number"
                min={1}
                value={config.sample.rows}
                onChange={(e) =>
                  config.sample &&
                  update({
                    ...config,
                    sample: { ...config.sample, rows: Math.max(1, Number(e.target.value) || 1) },
                  })
                }
              />
            </Field>
          </div>
        )}
      </div>
    </div>
  );
}
