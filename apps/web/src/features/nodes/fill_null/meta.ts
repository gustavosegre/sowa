import { PaintBucket } from "lucide-react";

import type { FillNullConfig } from "@/api/types";

import type { NodeMeta } from "../types";
import { summary } from "./summary";

export const meta: NodeMeta<FillNullConfig> = {
  type: "fill_null",
  label: "Preencher vazios",
  description: "Valor fixo, anterior/próximo (preencher para baixo) ou média.",
  category: "columns",
  icon: PaintBucket,
  inputs: ["in"],
  hasOutput: true,
  keywords: ["nulos", "vazios", "preencher para baixo", "coalesce"],
  next: ["calculated", "group_by"],
  defaultConfig: () => ({ rules: [], order_by: [] }),
  summary,
};
