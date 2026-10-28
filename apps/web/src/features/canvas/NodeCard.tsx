import { Handle, Position, type Node, type NodeProps } from "@xyflow/react";
import { AlertTriangle, CircleX, Lock, Plus } from "lucide-react";
import { memo, useState } from "react";

import { useCachedStats } from "@/api/hooks";
import type { NodeAnalysis, PipelineNode } from "@/api/types";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui";
import { getMeta, nodeSummary } from "@/features/nodes/registry";
import { CATEGORY_COLOR } from "@/features/nodes/types";
import { t } from "@/i18n/pt-BR";
import { cn, fmtInt } from "@/lib/utils";
import { usePipelineStore } from "@/stores/pipelineStore";

import { AddNodeMenu } from "./AddNodeMenu";

export interface CardData extends Record<string, unknown> {
  node: PipelineNode;
  analysis: NodeAnalysis | undefined;
  sourceName?: string;
}

export type CardNode = Node<CardData, "card">;

const HANDLE_LABELS: Record<string, string> = {
  left: "esquerda",
  right: "direita",
  main: "principal",
  lookup: "consulta",
};

function RowBadge({ id, analysis }: { id: string; analysis: NodeAnalysis | undefined }) {
  const stats = useCachedStats(id, analysis?.hash);
  if (!stats || stats.row_count == null) return null;
  const inputs = Object.values(stats.input_row_counts);
  const first = inputs[0];
  const changed = inputs.length === 1 && first !== undefined && first !== stats.row_count;
  return (
    <span className="font-mono text-[10px] text-muted-foreground" title="Linhas">
      {changed ? `${fmtInt(first)} → ${fmtInt(stats.row_count)}` : `${fmtInt(stats.row_count)} linhas`}
    </span>
  );
}

function Title({ node, fallback }: { node: PipelineNode; fallback: string }) {
  const [editing, setEditing] = useState(false);
  const setLabel = usePipelineStore((s) => s.setLabel);
  const label = node.ui.label || fallback;
  if (editing) {
    return (
      <input
        autoFocus
        defaultValue={label}
        className="nodrag h-5 min-w-0 flex-1 rounded border border-input bg-card px-1 text-[13px] font-semibold outline-none"
        onBlur={(e) => (
          setLabel(node.id, e.target.value === fallback ? "" : e.target.value),
          setEditing(false)
        )}
        onKeyDown={(e) => {
          if (e.key === "Enter") (e.target as HTMLInputElement).blur();
          if (e.key === "Escape") setEditing(false);
        }}
        aria-label={t.common.rename}
      />
    );
  }
  return (
    <span
      className="min-w-0 flex-1 truncate text-[13px] font-semibold"
      onDoubleClick={() => setEditing(true)}
      title={`${label} — clique duas vezes para renomear`}
    >
      {label}
    </span>
  );
}

function NodeCardImpl({ data, selected }: NodeProps<CardNode>) {
  const { node, analysis } = data;
  const meta = getMeta(node.type);
  const [menuOpen, setMenuOpen] = useState(false);
  if (!meta) return null;
  const Icon = meta.icon;
  const status = analysis?.status ?? "ok";
  const color = CATEGORY_COLOR[meta.category];
  const summary = nodeSummary(node.type, node.config);
  const firstError = analysis?.issues.find((i) => i.severity === "error");
  const warnings = analysis?.issues.filter((i) => i.severity === "warning").length ?? 0;
  const fallback = node.type === "source" && data.sourceName ? data.sourceName : meta.label;

  return (
    <div
      className={cn(
        "group relative w-[240px] rounded-lg border bg-card shadow-sm transition-shadow",
        selected && "shadow-md ring-2 ring-primary/60",
        status === "error" && "border-danger ring-danger/40",
        status === "blocked" && "opacity-55 grayscale",
      )}
      data-testid={`node-${node.id}`}
      data-status={status}
    >
      <div className="h-1 rounded-t-lg" style={{ background: color }} />
      {meta.inputs.map((h, i) => (
        <Handle
          key={h}
          id={h}
          type="target"
          position={Position.Left}
          style={{ top: meta.inputs.length === 1 ? "50%" : `${30 + i * 30}%` }}
          title={HANDLE_LABELS[h] ? `Entrada ${HANDLE_LABELS[h]}` : "Entrada"}
        />
      ))}
      <div className="flex flex-col gap-1 px-2.5 py-2">
        <div className="flex items-center gap-1.5">
          <span
            className="flex size-5 shrink-0 items-center justify-center rounded"
            style={{ background: `color-mix(in oklch, ${color} 15%, transparent)` }}
          >
            <Icon className="size-3.5" style={{ color }} />
          </span>
          <Title node={node} fallback={fallback} />
          {status === "error" && (
            <CircleX className="size-3.5 shrink-0 text-danger" aria-label={t.status.error} />
          )}
          {status === "blocked" && (
            <Lock className="size-3.5 shrink-0 text-muted-foreground" aria-label={t.status.blocked} />
          )}
          {status === "warning" && (
            <AlertTriangle className="size-3.5 shrink-0 text-warning" aria-label={t.status.warning} />
          )}
        </div>
        {summary && (
          <p className="line-clamp-2 break-words text-[11px] leading-snug text-muted-foreground">{summary}</p>
        )}
        {firstError && (
          <p className="line-clamp-2 text-[11px] leading-snug text-danger">{firstError.message}</p>
        )}
        {status === "blocked" && (
          <p className="text-[11px] text-muted-foreground">{analysis?.issues[0]?.message}</p>
        )}
        <div className="flex min-h-4 flex-wrap items-center gap-1">
          {analysis?.changed_columns.slice(0, 4).map((c) => (
            <span
              key={c}
              className="rounded px-1 text-[10px] font-medium"
              style={{ background: `color-mix(in oklch, ${color} 14%, transparent)`, color }}
            >
              {c}
            </span>
          ))}
          {(analysis?.changed_columns.length ?? 0) > 4 && (
            <span className="text-[10px] text-muted-foreground">
              +{(analysis?.changed_columns.length ?? 0) - 4}
            </span>
          )}
          <span className="flex-1" />
          {warnings > 0 && status !== "error" && <AlertTriangle className="size-3 text-warning" />}
          <RowBadge id={node.id} analysis={analysis} />
        </div>
      </div>
      {meta.hasOutput && (
        <>
          <Handle type="source" id="out" position={Position.Right} title="Saída" />
          <Popover open={menuOpen} onOpenChange={setMenuOpen}>
            <PopoverTrigger asChild>
              <button
                type="button"
                className={cn(
                  "nodrag absolute -right-8 top-1/2 flex size-5 -translate-y-1/2 cursor-pointer items-center justify-center rounded-full border bg-card text-muted-foreground opacity-0 shadow-sm transition-opacity hover:text-primary group-hover:opacity-100 focus-visible:opacity-100",
                  (selected || menuOpen) && "opacity-100",
                )}
                aria-label={t.editor.addAfter}
              >
                <Plus className="size-3.5" />
              </button>
            </PopoverTrigger>
            <PopoverContent side="right" align="start" className="w-60 p-1">
              <AddNodeMenu
                suggested={meta.next ?? []}
                onPick={(type) => {
                  setMenuOpen(false);
                  usePipelineStore.getState().addNode(type, {
                    connectFrom: node.id,
                    position: { x: node.ui.x + 290, y: node.ui.y },
                  });
                }}
              />
            </PopoverContent>
          </Popover>
        </>
      )}
    </div>
  );
}

export const NodeCard = memo(NodeCardImpl);
