import { StickyNote } from "lucide-react";

import type { NoteConfig } from "@/api/types";

import type { NodeMeta } from "../types";

export const meta: NodeMeta<NoteConfig> = {
  type: "note",
  label: "Nota",
  description: "Post-it no canvas, sem efeito nos dados.",
  category: "organize",
  icon: StickyNote,
  inputs: [],
  hasOutput: false,
  annotation: true,
  keywords: ["nota", "comentário", "post-it"],
  defaultConfig: () => ({ text: "" }),
  summary: (c) => c.text,
};
