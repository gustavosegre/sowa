import { renderFormula } from "@/api/hooks";
import type { CalculatedConfig, FilterConfig, GroupByConfig, Pipeline } from "@/api/types";
import { usePipelineStore, type Locale } from "@/stores/pipelineStore";

/**
 * Formulas are stored as text in the pipeline's locale. Switching locale
 * re-renders every formula from its AST on the server (CLAUDE.md §11).
 */
export async function switchLocale(pipeline: Pipeline, to: Locale): Promise<void> {
  const from = pipeline.settings.locale;
  if (from === to) return;
  const conv = (f: string) => (f.trim() ? renderFormula(f, from, to) : Promise.resolve(f));
  const configs: Record<string, Record<string, unknown>> = {};
  await Promise.all(
    pipeline.nodes.map(async (n) => {
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
  usePipelineStore.getState().setLocale(to, configs);
}
