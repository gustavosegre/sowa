import { createElement, type ComponentType } from "react";

/** Config panels per node type (React). Kept apart from `registry.ts` to avoid import cycles with the store. */
import type { FrameConfig, NoteConfig } from "@/api/types";
import { Field, Input, Select, Textarea } from "@/components/ui";
import { t } from "@/i18n/pt-BR";

import { ConfigPanel as CalculatedPanel } from "./calculated/ConfigPanel";
import { ConfigPanel as ConditionalPanel } from "./conditional/ConfigPanel";
import { ConfigPanel as JoinPanel } from "./join/ConfigPanel";
import { ConfigPanel as LookupPanel } from "./lookup/ConfigPanel";
import { ConfigPanel as PivotPanel } from "./pivot/ConfigPanel";
import {
  BinPanel,
  DatePartsPanel,
  DistinctPanel,
  FillNullPanel,
  ReplacePanel,
  SamplePanel,
  SplitPanel,
  TextCleanPanel,
  UnpivotPanel,
} from "./simple/panels";
import { ConfigPanel as UnionPanel } from "./union/ConfigPanel";
import { ConfigPanel as WindowPanel } from "./window/ConfigPanel";
import { ConfigPanel as CastPanel } from "./cast/ConfigPanel";
import { ConfigPanel as FilterPanel } from "./filter/ConfigPanel";
import { ConfigPanel as GroupByPanel } from "./group_by/ConfigPanel";
import { ConfigPanel as OutputPanel } from "./output/ConfigPanel";
import { ConfigPanel as SelectPanel } from "./select/ConfigPanel";
import type { ConfigPanelProps } from "./shared/panel";
import { ConfigPanel as SortPanel } from "./sort/ConfigPanel";
import { ConfigPanel as SourcePanel } from "./source/ConfigPanel";

export const FRAME_COLORS = ["slate", "blue", "green", "amber", "rose", "violet"] as const;

function NotePanel({ config, update }: ConfigPanelProps<NoteConfig>) {
  return (
    <Textarea
      rows={8}
      value={config.text}
      placeholder={t.nodes.note.placeholder}
      onChange={(e) => update({ ...config, text: e.target.value })}
    />
  );
}

function FramePanel({ config, update }: ConfigPanelProps<FrameConfig>) {
  return (
    <div className="flex flex-col gap-3">
      <Field label={t.nodes.frame.title}>
        <Input value={config.title} onChange={(e) => update({ ...config, title: e.target.value })} />
      </Field>
      <Field label={t.nodes.frame.color}>
        <Select
          value={config.color}
          options={FRAME_COLORS.map((c) => ({ value: c, label: c }))}
          onChange={(color) => update({ ...config, color })}
        />
      </Field>
    </div>
  );
}

type AnyPanelProps = ConfigPanelProps<Record<string, unknown>>;

// Each panel is typed with its own config; the map stores them type-erased.
const PANELS = {
  source: SourcePanel,
  select: SelectPanel,
  cast: CastPanel,
  calculated: CalculatedPanel,
  filter: FilterPanel,
  sort: SortPanel,
  group_by: GroupByPanel,
  output: OutputPanel,
  note: NotePanel,
  frame: FramePanel,
  distinct: DistinctPanel,
  sample: SamplePanel,
  text_clean: TextCleanPanel,
  replace: ReplacePanel,
  fill_null: FillNullPanel,
  date_parts: DatePartsPanel,
  bin: BinPanel,
  split: SplitPanel,
  conditional: ConditionalPanel,
  unpivot: UnpivotPanel,
  window: WindowPanel,
  pivot: PivotPanel,
  join: JoinPanel,
  union: UnionPanel,
  lookup: LookupPanel,
} as unknown as Record<string, ComponentType<AnyPanelProps> | undefined>;

/** Renders the config panel of a node type. Components are static; only the lookup is dynamic. */
export function NodePanel({ type, ...props }: AnyPanelProps & { type: string }) {
  const panel = PANELS[type];
  return panel ? createElement(panel, props) : null;
}
