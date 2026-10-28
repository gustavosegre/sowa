import { CopyMinus } from "lucide-react";

import type { DistinctConfig } from "@/api/types";

import type { NodeMeta } from "../types";
import { summary } from "./summary";

export const meta: NodeMeta<DistinctConfig> = {
  type: "distinct",
  label: "Remover duplicatas",
  description: "Linha inteira ou por chaves, mantendo a primeira ou a última.",
  category: "rows",
  icon: CopyMinus,
  inputs: ["in"],
  hasOutput: true,
  keywords: ["duplicadas", "únicos", "distinto", "repetidos"],
  next: ["sort", "group_by", "output"],
  defaultConfig: () => ({ keys: [], keep: "first", order_by: [] }),
  summary,
};
