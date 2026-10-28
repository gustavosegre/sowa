import { Boxes } from "lucide-react";

import type { SubflowConfig } from "@/api/types";

import type { NodeMeta } from "../types";
import { summary } from "./summary";

export const meta: NodeMeta<SubflowConfig> = {
  type: "subflow",
  label: "Sub-fluxo",
  description: "Um template salvo usado como um único nó.",
  category: "advanced",
  icon: Boxes,
  inputs: ["in_0"],
  hasOutput: true,
  hidden: true,
  inputsFor: (c) => c.flow.inputs.map((_, k) => `in_${k}`),
  inputLabel: (c, h) => c.flow.inputs[Number(h.slice(3))]?.name ?? null,
  keywords: ["template", "sub-fluxo", "reutilizar"],
  next: ["output", "filter"],
  defaultConfig: () => ({
    template_id: null,
    template_name: "",
    template_version: 0,
    flow: { locale: "pt-BR", nodes: [], edges: [], inputs: [], output: null },
  }),
  summary,
};
