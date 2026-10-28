import { Merge } from "lucide-react";

import type { JoinConfig } from "@/api/types";

import type { NodeMeta } from "../types";
import { summary } from "./summary";

export const meta: NodeMeta<JoinConfig> = {
  type: "join",
  label: "Juntar",
  description: "Junta duas tabelas por chaves (inner, left, right, full, anti, semi).",
  category: "combine",
  icon: Merge,
  inputs: ["left", "right"],
  hasOutput: true,
  keywords: ["join", "mesclar", "cruzar", "relacionar"],
  next: ["select", "filter", "group_by"],
  defaultConfig: () => ({ how: "left", keys: [], suffix: "_2" }),
  summary,
};
