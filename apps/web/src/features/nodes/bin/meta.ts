import { Ruler } from "lucide-react";

import type { BinConfig } from "@/api/types";

import type { NodeMeta } from "../types";
import { summary } from "./summary";

export const meta: NodeMeta<BinConfig> = {
  type: "bin",
  label: "Faixas",
  description: "Agrupa números em faixas (limites manuais ou intervalos iguais).",
  category: "columns",
  icon: Ruler,
  inputs: ["in"],
  hasOutput: true,
  keywords: ["faixa", "intervalo", "classes", "bucket", "histograma"],
  next: ["group_by", "pivot"],
  defaultConfig: () => ({ column: "", name: "", mode: "manual", boundaries: [], labels: [], count: 5 }),
  summary,
};
