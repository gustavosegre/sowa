/** Front catalog of node types (metadata only: no React panels, no store imports). */
import { meta as calculated } from "./calculated/meta";
import { meta as cast } from "./cast/meta";
import { meta as filter } from "./filter/meta";
import { meta as frame } from "./frame/meta";
import { meta as groupBy } from "./group_by/meta";
import { meta as note } from "./note/meta";
import { meta as output } from "./output/meta";
import { meta as select } from "./select/meta";
import { meta as sort } from "./sort/meta";
import { meta as source } from "./source/meta";
import { meta as distinct } from "./distinct/meta";
import { meta as sample } from "./sample/meta";
import { meta as textClean } from "./text_clean/meta";
import { meta as replace } from "./replace/meta";
import { meta as fillNull } from "./fill_null/meta";
import { meta as dateParts } from "./date_parts/meta";
import { meta as bin } from "./bin/meta";
import { meta as split } from "./split/meta";
import { meta as conditional } from "./conditional/meta";
import { meta as unpivot } from "./unpivot/meta";
import { meta as windowNode } from "./window/meta";
import { meta as pivot } from "./pivot/meta";
import { meta as join } from "./join/meta";
import { meta as union } from "./union/meta";
import { meta as lookup } from "./lookup/meta";
import type { NodeMeta } from "./types";

// Each meta is typed with its own config; the registry stores them type-erased.
const ALL = [
  source,
  select,
  cast,
  calculated,
  conditional,
  split,
  textClean,
  replace,
  fillNull,
  dateParts,
  bin,
  filter,
  sort,
  distinct,
  sample,
  groupBy,
  pivot,
  unpivot,
  windowNode,
  join,
  union,
  lookup,
  output,
  note,
  frame,
] as unknown as NodeMeta[];

const BY_TYPE = new Map(ALL.map((m) => [m.type, m]));

export function getMeta(type: string): NodeMeta | undefined {
  return BY_TYPE.get(type);
}

export function allMetas(): NodeMeta[] {
  return ALL;
}

export function nodeSummary(type: string, config: Record<string, unknown>): string {
  const m = getMeta(type);
  if (!m) return "";
  try {
    return m.summary(config);
  } catch {
    return "";
  }
}
