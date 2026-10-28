import { CalendarDays } from "lucide-react";

import type { DatePartsConfig } from "@/api/types";

import type { NodeMeta } from "../types";
import { summary } from "./summary";

export const meta: NodeMeta<DatePartsConfig> = {
  type: "date_parts",
  label: "Extrair de data",
  description: "Ano, trimestre, mês, semana, dia da semana, nomes em pt-BR.",
  category: "columns",
  icon: CalendarDays,
  inputs: ["in"],
  hasOutput: true,
  keywords: ["ano", "mês", "trimestre", "semana", "dia da semana"],
  next: ["group_by", "pivot"],
  defaultConfig: () => ({ column: "", parts: ["year", "month"], prefix: null }),
  summary,
};
