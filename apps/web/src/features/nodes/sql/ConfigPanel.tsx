import { useMemo } from "react";

import type { SqlConfig } from "@/api/types";
import { Field, Textarea } from "@/components/ui";
import { TypeIcon } from "@/components/TypeIcon";
import { useNodeAnalysis } from "@/features/editor/analysis";
import { t } from "@/i18n/pt-BR";
import { usePipelineStore } from "@/stores/pipelineStore";

import { getMeta } from "../registry";
import type { ConfigPanelProps } from "../shared/panel";

function tableName(handle: string): string {
  const i = Number(handle.split("_")[1] ?? 0);
  return i === 0 ? "input" : `input_${i}`;
}

export function ConfigPanel({ node, config, update }: ConfigPanelProps<SqlConfig>) {
  const analysis = useNodeAnalysis(node.id);
  const allEdges = usePipelineStore((s) => s.pipeline.edges);
  const edges = useMemo(() => allEdges.filter((e) => e.target === node.id), [allEdges, node.id]);
  const nodes = usePipelineStore((s) => s.pipeline.nodes);
  const inputs = Object.entries(analysis?.input_columns ?? {}).sort(([a], [b]) => a.localeCompare(b));
  return (
    <div className="flex flex-col gap-3">
      <Field label={t.sql.query} hint={t.sql.hint}>
        <Textarea
          rows={10}
          spellCheck={false}
          className="font-mono text-[12px]"
          value={config.query}
          onChange={(e) => update({ ...config, query: e.target.value })}
        />
      </Field>
      <div className="flex flex-col gap-2">
        <span className="text-xs font-medium text-muted-foreground">{t.sql.tables}</span>
        {!inputs.length && <p className="text-xs text-muted-foreground">{t.sql.notConnected}</p>}
        {inputs.map(([handle, cols]) => {
          const up = edges.find((e) => e.target_handle === handle)?.source;
          const upNode = nodes.find((n) => n.id === up);
          const label = upNode ? upNode.ui.label || (getMeta(upNode.type)?.label ?? upNode.type) : "";
          return (
            <div key={handle} className="rounded-md border p-2">
              <p className="text-xs">
                <code className="font-mono font-semibold text-cat-advanced">{tableName(handle)}</code>
                <span className="text-muted-foreground"> · {label}</span>
              </p>
              <ul className="mt-1 flex flex-wrap gap-1">
                {cols.map((c) => (
                  <li
                    key={c.name}
                    className="flex items-center gap-1 rounded bg-muted px-1 font-mono text-[11px]"
                  >
                    <TypeIcon type={c.type} />
                    {c.name}
                  </li>
                ))}
              </ul>
            </div>
          );
        })}
      </div>
    </div>
  );
}
