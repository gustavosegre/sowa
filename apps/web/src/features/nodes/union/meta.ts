import { Layers } from "lucide-react";

import type { UnionConfig } from "@/api/types";

import type { NodeMeta } from "../types";
import { summary } from "./summary";

export const meta: NodeMeta<UnionConfig> = {
  type: "union",
  label: "Empilhar",
  description: "Empilha tabelas alinhando por nome ou posição.",
  category: "combine",
  icon: Layers,
  inputs: ["in_0", "in_1"],
  hasOutput: true,
  keywords: ["empilhar", "acrescentar", "append", "union", "concatenar"],
  next: ["distinct", "group_by"],
  defaultConfig: () => ({ mode: "by_name", source_column: null }),
  summary,
};
