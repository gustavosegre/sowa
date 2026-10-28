import { NodeResizer, type Node, type NodeProps } from "@xyflow/react";
import { memo } from "react";

import type { FrameConfig, NoteConfig, PipelineNode } from "@/api/types";
import { t } from "@/i18n/pt-BR";
import { cn } from "@/lib/utils";
import { usePipelineStore } from "@/stores/pipelineStore";

export type NoteNodeT = Node<{ node: PipelineNode }, "note">;
export type FrameNodeT = Node<{ node: PipelineNode }, "frame">;

function NoteImpl({ data, selected }: NodeProps<NoteNodeT>) {
  const cfg = data.node.config as NoteConfig;
  const update = usePipelineStore((s) => s.updateConfig);
  return (
    <div
      className={cn(
        "flex h-full min-h-24 w-[220px] flex-col rounded-md border border-yellow-300/70 bg-yellow-100 p-2 shadow-sm dark:border-yellow-600/40 dark:bg-yellow-900/40",
        selected && "ring-2 ring-primary/50",
      )}
    >
      <textarea
        className="nodrag nowheel h-full min-h-20 w-full resize-none bg-transparent text-[12px] leading-snug text-yellow-950 outline-none placeholder:text-yellow-800/50 dark:text-yellow-50"
        value={cfg.text}
        placeholder={t.nodes.note.placeholder}
        onChange={(e) => update(data.node.id, { ...cfg, text: e.target.value })}
        aria-label="Nota"
      />
    </div>
  );
}

const FRAME_BG: Record<string, string> = {
  slate: "oklch(0.6 0.02 260)",
  blue: "oklch(0.6 0.13 240)",
  green: "oklch(0.62 0.13 155)",
  amber: "oklch(0.72 0.14 75)",
  rose: "oklch(0.62 0.17 15)",
  violet: "oklch(0.58 0.16 295)",
};

function FrameImpl({ data, selected }: NodeProps<FrameNodeT>) {
  const cfg = data.node.config as FrameConfig;
  const setUi = usePipelineStore((s) => s.setUi);
  const color = FRAME_BG[cfg.color] ?? FRAME_BG.slate;
  return (
    <>
      <NodeResizer
        isVisible={selected}
        minWidth={200}
        minHeight={120}
        onResizeEnd={(_, p) => setUi(data.node.id, { x: p.x, y: p.y, width: p.width, height: p.height })}
      />
      <div
        className="h-full w-full rounded-xl border-2 border-dashed"
        style={{
          borderColor: `color-mix(in oklch, ${color} 50%, transparent)`,
          background: `color-mix(in oklch, ${color} 7%, transparent)`,
        }}
      >
        <div className="px-3 py-1.5 text-[13px] font-semibold" style={{ color }}>
          {cfg.title}
        </div>
      </div>
    </>
  );
}

export const NoteNode = memo(NoteImpl);
export const FrameNode = memo(FrameImpl);
