import { Download } from "lucide-react";

import type { OutputConfig } from "@/api/types";

import type { NodeMeta } from "../types";
import { summary } from "./summary";

export const meta: NodeMeta<OutputConfig> = {
  type: "output",
  label: "Exportar",
  description: "Gera o dataset final em CSV, Parquet, XLSX ou JSON.",
  category: "output",
  icon: Download,
  inputs: ["in"],
  hasOutput: false,
  keywords: ["exportar", "salvar", "baixar", "csv", "parquet", "excel"],
  defaultConfig: () => ({
    format: "csv",
    filename: "dataset",
    preset: "excel_br",
    csv: {
      delimiter: ",",
      encoding: "utf-8",
      decimal_separator: ".",
      date_format: "%Y-%m-%d",
      datetime_format: "%Y-%m-%d %H:%M:%S",
      header: true,
      quote: '"',
    },
    parquet: { compression: "zstd", row_group_size: null },
  }),
  summary,
};
