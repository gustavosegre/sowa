import { FileSpreadsheet } from "lucide-react";

import type { SourceConfig } from "@/api/types";

import type { NodeMeta } from "../types";
import { summary } from "./summary";

export const meta: NodeMeta<SourceConfig> = {
  type: "source",
  label: "Fonte",
  description: "Lê um arquivo importado.",
  category: "input",
  icon: FileSpreadsheet,
  inputs: [],
  hasOutput: true,
  keywords: ["arquivo", "csv", "planilha", "entrada"],
  next: ["cast", "filter", "select", "calculated", "group_by"],
  defaultConfig: () => ({ source_id: "", sample: null }),
  summary,
};
