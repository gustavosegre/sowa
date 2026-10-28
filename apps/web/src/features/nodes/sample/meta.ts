import { Dices } from "lucide-react";

import type { SampleNodeConfig } from "@/api/types";

import type { NodeMeta } from "../types";
import { summary } from "./summary";

export const meta: NodeMeta<SampleNodeConfig> = {
  type: "sample",
  label: "Amostra / Limite",
  description: "Primeiras N linhas, N aleatórias ou uma porcentagem.",
  category: "rows",
  icon: Dices,
  inputs: ["in"],
  hasOutput: true,
  keywords: ["amostra", "limite", "top", "aleatório"],
  next: ["output"],
  defaultConfig: () => ({ mode: "first", rows: 1000, percent: 10, seed: 42 }),
  summary,
};
