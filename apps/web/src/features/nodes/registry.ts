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
import type { NodeMeta } from "./types";

// Each meta is typed with its own config; the registry stores them type-erased.
const ALL = [
  source,
  select,
  cast,
  calculated,
  filter,
  sort,
  groupBy,
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
