import { DatabaseZap } from "lucide-react";

import type { SqlConfig } from "@/api/types";

import type { NodeMeta } from "../types";
import { summary } from "./summary";

export const meta: NodeMeta<SqlConfig> = {
  type: "sql",
  label: "SQL",
  description: "SELECT livre sobre input, input_1…; só leitura.",
  category: "advanced",
  icon: DatabaseZap,
  inputs: ["in_0"],
  hasOutput: true,
  keywords: ["sql", "consulta", "select", "duckdb", "avançado"],
  next: ["output", "filter"],
  defaultConfig: () => ({ query: "SELECT *\nFROM input" }),
  summary,
};
