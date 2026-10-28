/**
 * Keyboard-accessible way to wire a node's inputs (CLAUDE.md §14: "tudo acessível por
 * teclado"): one select per input handle, listing the nodes that can feed it.
 */
import { useMemo } from "react";

import { useSources } from "@/api/hooks";
import type { Pipeline, PipelineNode } from "@/api/types";
import { Field, Select } from "@/components/ui";
import { inputHandles, lastVariadicInput } from "@/features/nodes/handles";
import { getMeta } from "@/features/nodes/registry";
import { t } from "@/i18n/pt-BR";
import { usePipelineStore } from "@/stores/pipelineStore";

import { useProjectId } from "./project";

const NONE = "__none__";

/** The node itself and everything downstream of it (connecting them would create a cycle). */
function downstream(pipeline: Pipeline, id: string): Set<string> {
  const seen = new Set([id]);
  const stack = [id];
  for (let cur = stack.pop(); cur !== undefined; cur = stack.pop()) {
    for (const e of pipeline.edges) {
      if (e.source === cur && !seen.has(e.target)) {
        seen.add(e.target);
        stack.push(e.target);
      }
    }
  }
  return seen;
}

export function InputsEditor({ node }: { node: PipelineNode }) {
  const pipeline = usePipelineStore((s) => s.pipeline);
  const { data: sources } = useSources(useProjectId());
  const meta = getMeta(node.type);

  const options = useMemo(() => {
    const blocked = downstream(pipeline, node.id);
    const names = new Map((sources ?? []).map((s) => [s.id, s.name]));
    const candidates = pipeline.nodes.filter((n) => {
      const m = getMeta(n.type);
      return m?.hasOutput && !m.annotation && !blocked.has(n.id);
    });
    const label = (n: PipelineNode) =>
      n.ui.label ||
      (n.type === "source"
        ? names.get(typeof n.config.source_id === "string" ? n.config.source_id : "")
        : undefined) ||
      getMeta(n.type)?.label ||
      n.type;
    // Same label twice (a duplicated node): number them in canvas order.
    const count = new Map<string, number>();
    for (const n of candidates) count.set(label(n), (count.get(label(n)) ?? 0) + 1);
    const seen = new Map<string, number>();
    return candidates.map((n) => {
      const base = label(n);
      const i = (seen.get(base) ?? 0) + 1;
      seen.set(base, i);
      return { value: n.id, label: (count.get(base) ?? 0) > 1 ? `${base} (${i})` : base };
    });
  }, [pipeline, node.id, sources]);

  if (!meta || meta.inputs.length === 0) return null;
  const handles = inputHandles(meta, lastVariadicInput(pipeline.edges, node.id), node.config);
  const store = usePipelineStore.getState();

  return (
    <fieldset className="flex flex-col gap-2 rounded-md border p-2">
      <legend className="px-1 text-xs font-medium text-muted-foreground">{t.inputs.title}</legend>
      {handles.map((h) => {
        const current = pipeline.edges.find((e) => e.target === node.id && e.target_handle === h);
        return (
          <Field key={h} label={t.inputs.handle(h, meta.inputLabel?.(node.config, h))}>
            <Select
              value={current?.source ?? NONE}
              options={[{ value: NONE, label: t.inputs.none }, ...options]}
              onChange={(v) => {
                if (v === NONE) {
                  if (current) store.removeEdges([current.id]);
                } else {
                  store.connect(v, node.id, h);
                }
              }}
            />
          </Field>
        );
      })}
    </fieldset>
  );
}
