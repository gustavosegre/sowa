import { Columns3 } from "lucide-react";

import type { SelectConfig } from "@/api/types";

import type { NodeMeta } from "../types";
import { summary } from "./summary";

export const meta: NodeMeta<SelectConfig> = {
  type: "select",
  label: "Selecionar colunas",
  description: "Escolher, reordenar, renomear e remover colunas.",
  category: "columns",
  icon: Columns3,
  inputs: ["in"],
  hasOutput: true,
  keywords: ["remover", "renomear", "reordenar", "colunas", "manter"],
  next: ["filter", "calculated", "output"],
  defaultConfig: () => ({ mode: "drop", columns: [], renames: {} }),
  summary,
};
