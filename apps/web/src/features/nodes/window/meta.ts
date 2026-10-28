import { ListOrdered } from "lucide-react";

import type { WindowConfig } from "@/api/types";

import type { NodeMeta } from "../types";
import { summary } from "./summary";

export const meta: NodeMeta<WindowConfig> = {
  type: "window",
  label: "Janela",
  description: "Acumulado, ranking, anterior/próximo, % do total, média móvel.",
  category: "aggregate",
  icon: ListOrdered,
  inputs: ["in"],
  hasOutput: true,
  keywords: ["acumulado", "ranking", "anterior", "média móvel", "percentual", "window"],
  next: ["filter", "output"],
  defaultConfig: () => ({ partition_by: [], order_by: [], items: [] }),
  summary,
};
