import { Frame } from "lucide-react";

import type { FrameConfig } from "@/api/types";

import type { NodeMeta } from "../types";

export const meta: NodeMeta<FrameConfig> = {
  type: "frame",
  label: "Moldura",
  description: "Agrupa nós visualmente com título e cor.",
  category: "organize",
  icon: Frame,
  inputs: [],
  hasOutput: false,
  annotation: true,
  keywords: ["moldura", "grupo", "seção"],
  defaultConfig: () => ({ title: "Etapa", color: "slate" }),
  summary: (c) => c.title,
};
