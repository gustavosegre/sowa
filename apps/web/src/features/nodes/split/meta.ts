import { Split } from "lucide-react";

import type { SplitConfig } from "@/api/types";

import type { NodeMeta } from "../types";
import { summary } from "./summary";

export const meta: NodeMeta<SplitConfig> = {
  type: "split",
  label: "Dividir coluna",
  description: "Por delimitador, posição ou expressão regular (Texto para colunas).",
  category: "columns",
  icon: Split,
  inputs: ["in"],
  hasOutput: true,
  keywords: ["texto para colunas", "separar", "dividir", "split"],
  next: ["cast", "select"],
  defaultConfig: () => ({
    column: "",
    mode: "delimiter",
    delimiter: ";",
    positions: [],
    pattern: "",
    parts: 2,
    names: [],
    keep_original: true,
    trim: true,
  }),
  summary,
};
