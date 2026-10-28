import { Filter } from "lucide-react";

import type { FilterConfig } from "@/api/types";

import type { NodeMeta } from "../types";
import { summary } from "./summary";

export const meta: NodeMeta<FilterConfig> = {
  type: "filter",
  label: "Filtrar",
  description: "Mantém só as linhas que atendem às condições.",
  category: "rows",
  icon: Filter,
  inputs: ["in"],
  hasOutput: true,
  keywords: ["filtro", "condição", "onde", "linhas"],
  next: ["group_by", "sort", "calculated", "output"],
  defaultConfig: () => ({ mode: "rules", rules: { kind: "group", op: "and", conditions: [] }, formula: "" }),
  summary,
};
