import { renderFormula } from "@/api/hooks";
import type {
  CalculatedConfig,
  FilterConfig,
  Flow,
  GroupByConfig,
  Pipeline,
  PipelineNode,
} from "@/api/types";
import { usePipelineStore, type Locale } from "@/stores/pipelineStore";

/**
 * Formulas are stored as text in the pipeline's locale. Switching locale
 * re-renders every formula from its AST on the server (CLAUDE.md §11).
 */
export async function switchLocale(pipeline: Pipeline, to: Locale): Promise<void> {
  const from = pipeline.settings.locale;
  if (from === to) return;
  usePipelineStore.getState().setLocale(to, await convertConfigs(pipeline.nodes, from, to));
}

/** A template's nodes in another locale (to insert them as editable nodes). */
export async function localizeFlow(flow: Flow, to: Locale): Promise<Flow> {
  if (flow.locale === to) return flow;
  const configs = await convertConfigs(flow.nodes, flow.locale, to);
  return {
    ...flow,
    locale: to,
    nodes: flow.nodes.map((n) => (configs[n.id] ? { ...n, config: configs[n.id] ?? n.config } : n)),
  };
}

/** Configs (by node id) of the nodes whose formulas change. Sub-flows keep their own locale. */
async function convertConfigs(
  nodes: PipelineNode[],
  from: Locale,
  to: Locale,
): Promise<Record<string, Record<string, unknown>>> {
  const conv = (f: string) => (f.trim() ? renderFormula(f, from, to) : Promise.resolve(f));
  const configs: Record<string, Record<string, unknown>> = {};
  await Promise.all(
    nodes.map(async (n) => {
      if (n.type === "calculated") {
        const c = n.config as CalculatedConfig;
        configs[n.id] = { ...c, formula: await conv(c.formula) };
      } else if (n.type === "filter") {
        const c = n.config as FilterConfig;
        configs[n.id] = { ...c, formula: await conv(c.formula) };
      } else if (n.type === "group_by") {
        const c = n.config as GroupByConfig;
        const measures = await Promise.all(
          c.measures.map(async (m) => ({ ...m, formula: await conv(m.formula) })),
        );
        configs[n.id] = { ...c, measures };
      }
    }),
  );
  return configs;
}
