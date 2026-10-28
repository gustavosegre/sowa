import { ArrowRightLeft } from "lucide-react";

import type { UnpivotConfig } from "@/api/types";

import type { NodeMeta } from "../types";
import { summary } from "./summary";

export const meta: NodeMeta<UnpivotConfig> = {
  type: "unpivot",
  label: "Despivotar",
  description: "Transforma colunas em linhas (atributo, valor).",
  category: "aggregate",
  icon: ArrowRightLeft,
  inputs: ["in"],
  hasOutput: true,
  keywords: ["colunas em linhas", "unpivot", "melt", "transpor"],
  next: ["filter", "group_by"],
  defaultConfig: () => ({ columns: [], name_column: "atributo", value_column: "valor", drop_nulls: false }),
  summary,
};
