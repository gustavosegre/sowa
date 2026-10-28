import type { Rectangle } from "@glideapps/glide-data-grid";
import {
  BarChart3,
  ChevronDown,
  ChevronUp,
  Columns2,
  Copy,
  Filter,
  Group,
  Pencil,
  Shapes,
  SortAsc,
  SortDesc,
  Sigma,
  Trash2,
} from "lucide-react";
import { useEffect, useState } from "react";

import { ApiError, errorIssue } from "@/api/client";
import { usePreview, useStats } from "@/api/hooks";
import type { Column } from "@/api/types";
import { IssueList } from "@/components/IssueList";
import { TYPE_OPTIONS } from "@/components/TypeIcon";
import {
  Badge,
  Button,
  Dialog,
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
  Input,
  Spinner,
} from "@/components/ui";
import { useAnalysis, useServerPipeline } from "@/features/editor/analysis";
import { getMeta } from "@/features/nodes/registry";
import { t } from "@/i18n/pt-BR";
import { fmtInt } from "@/lib/utils";
import { usePipelineStore } from "@/stores/pipelineStore";
import { useUiStore } from "@/stores/uiStore";

import * as actions from "./columnActions";
import { DataGrid } from "./DataGrid";
import { filterValue } from "./format";
import { ProfilePanel } from "./ProfilePanel";

interface MenuState {
  column: Column;
  bounds: Rectangle;
  value?: { v: unknown };
}

function NodeGrid({
  nodeId,
  hash,
  columns,
  highlight,
  onHeaderMenu,
  onCellMenu,
}: {
  nodeId: string;
  hash: string | null | undefined;
  columns: Column[];
  highlight?: Set<string>;
  onHeaderMenu?: (c: Column, b: Rectangle) => void;
  onCellMenu?: (c: Column, v: unknown, b: Rectangle) => void;
}) {
  const pipeline = useServerPipeline((s) => s.pipeline);
  const q = usePreview(pipeline, nodeId, hash);
  const pages = q.data?.pages ?? [];
  if (q.error) {
    const e = q.error instanceof ApiError ? q.error : null;
    return (
      <div className="p-3">
        <IssueList issues={e?.issues.length ? e.issues : [errorIssue(q.error)]} />
      </div>
    );
  }
  if (!pages.length) {
    return (
      <div className="flex h-full items-center justify-center text-muted-foreground">
        <Spinner />
      </div>
    );
  }
  return (
    <DataGrid
      columns={columns}
      pages={pages}
      highlight={highlight}
      onHeaderMenu={onHeaderMenu}
      onCellMenu={onCellMenu}
      onNeedMore={() => {
        if (q.hasNextPage && !q.isFetchingNextPage) void q.fetchNextPage();
      }}
    />
  );
}

export function PreviewPanel() {
  const selectedId = usePipelineStore((s) => s.selectedId);
  const node = usePipelineStore((s) => s.pipeline.nodes.find((n) => n.id === s.selectedId));
  const serverPipeline = useServerPipeline((s) => s.pipeline);
  const { data: analysis } = useAnalysis();
  const ui = useUiStore();
  const [menu, setMenu] = useState<MenuState | null>(null);
  const [renaming, setRenaming] = useState<string | null>(null);
  const a = selectedId ? analysis?.nodes[selectedId] : undefined;
  const meta = node ? getMeta(node.type) : undefined;
  const ok = a && (a.status === "ok" || a.status === "warning") && a.columns;
  // The output node has no output of its own: preview what it will write.
  const inputEdge = node
    ? serverPipeline.edges.find((e) => e.target === node.id && e.target_handle === "in")
    : undefined;
  const upstreamId = inputEdge?.source ?? null;
  const upstream = upstreamId ? analysis?.nodes[upstreamId] : undefined;
  const previewId = meta?.hasOutput ? selectedId : upstreamId;
  const previewAnalysis = meta?.hasOutput ? a : upstream;
  const stats = useStats(serverPipeline, selectedId, ok ? a.hash : null);
  const sampled = serverPipeline.nodes.some((n) => n.type === "source" && n.config.sample != null);

  const highlight = new Set(a?.changed_columns ?? []);
  const columns = previewAnalysis?.columns ?? [];
  const removed = upstream?.columns?.filter((c) => !a?.columns?.some((x) => x.name === c.name)) ?? [];
  const inRows = stats.data?.input_row_counts.in;
  const outRows = stats.data?.row_count;
  const runtimeIssues = stats.data?.issues ?? [];

  const header = (
    <div className="flex h-9 shrink-0 items-center gap-2 border-b px-3">
      <h2 className="text-[12px] font-semibold uppercase tracking-wide text-muted-foreground">
        {t.preview.title}
      </h2>
      {node && <span className="truncate text-[13px] font-medium">{node.ui.label || meta?.label}</span>}
      {ok && (
        <span className="font-mono text-[11px] text-muted-foreground">
          {stats.isLoading
            ? t.preview.counting
            : outRows != null
              ? inRows != null && inRows !== outRows
                ? `${fmtInt(inRows)} → ${fmtInt(outRows)} linhas`
                : `${fmtInt(outRows)} linhas`
              : null}
          {" · "}
          {a.columns?.length ?? 0} colunas
        </span>
      )}
      {runtimeIssues.length > 0 && <Badge tone="warning">{runtimeIssues.length} aviso(s)</Badge>}
      {sampled && <Badge tone="primary">{t.preview.sampleBanner}</Badge>}
      <span className="flex-1" />
      {meta?.hasOutput && upstreamId && meta.inputs.length === 1 && (
        <Button
          variant={ui.compareMode ? "subtle" : "ghost"}
          size="sm"
          onClick={() => ui.setCompare(!ui.compareMode)}
          aria-pressed={ui.compareMode}
        >
          <Columns2 /> {t.preview.compare}
        </Button>
      )}
      <Button
        variant="ghost"
        size="iconSm"
        onClick={ui.togglePreview}
        aria-label={ui.previewCollapsed ? t.preview.expand : t.preview.collapse}
      >
        {ui.previewCollapsed ? <ChevronUp /> : <ChevronDown />}
      </Button>
    </div>
  );

  if (ui.previewCollapsed) return header;

  let body: React.ReactNode;
  if (!node || !previewId) {
    body = <p className="p-4 text-muted-foreground">{t.preview.noNode}</p>;
  } else if (!previewAnalysis) {
    // A node just added: its analysis is still on the way.
    body = (
      <p className="flex items-center gap-2 p-4 text-muted-foreground">
        <Spinner /> {t.common.loading}
      </p>
    );
  } else if (!(previewAnalysis.status === "ok" || previewAnalysis.status === "warning")) {
    body = (
      <div className="flex flex-col gap-2 p-3">
        <p className="text-muted-foreground">{t.preview.blocked}</p>
        <IssueList issues={a?.issues ?? []} />
      </div>
    );
  } else if (ui.compareMode && upstreamId && upstream?.columns && meta?.hasOutput) {
    body = (
      <div className="grid h-full min-h-0 grid-cols-2 divide-x">
        <div className="flex min-h-0 flex-col">
          <p className="border-b px-3 py-1 text-[11px] font-medium text-muted-foreground">
            {t.preview.compareInput} {inRows != null && `· ${fmtInt(inRows)} linhas`}
          </p>
          <div className="min-h-0 flex-1">
            <NodeGrid nodeId={upstreamId} hash={upstream.hash} columns={upstream.columns} />
          </div>
        </div>
        <div className="flex min-h-0 flex-col">
          <p className="flex gap-2 border-b px-3 py-1 text-[11px] font-medium text-muted-foreground">
            {t.preview.compareOutput}
            {inRows != null && outRows != null && inRows > outRows && (
              <span className="text-danger">{t.preview.filteredRows(fmtInt(inRows - outRows))}</span>
            )}
            {removed.length > 0 && (
              <span className="text-danger" title={removed.map((c) => c.name).join(", ")}>
                {t.preview.removedColumns(removed.length)}
              </span>
            )}
            {highlight.size > 0 && <span className="text-primary">{[...highlight].join(", ")}</span>}
          </p>
          <div className="min-h-0 flex-1">
            <NodeGrid
              nodeId={previewId}
              hash={previewAnalysis.hash}
              columns={columns}
              highlight={highlight}
            />
          </div>
        </div>
      </div>
    );
  } else {
    body = (
      <div className="flex h-full min-h-0">
        <div className="flex min-w-0 flex-1 flex-col">
          {runtimeIssues.length > 0 && (
            <div className="max-h-28 shrink-0 overflow-auto border-b p-2">
              <IssueList issues={runtimeIssues} />
            </div>
          )}
          <div className="relative min-h-0 flex-1">
            <NodeGrid
              nodeId={previewId}
              hash={previewAnalysis.hash}
              columns={columns}
              highlight={highlight}
              onHeaderMenu={meta?.hasOutput ? (column, bounds) => setMenu({ column, bounds }) : undefined}
              onCellMenu={
                meta?.hasOutput ? (column, v, bounds) => setMenu({ column, bounds, value: { v } }) : undefined
              }
            />
          </div>
        </div>
        {ui.profileColumn && columns.some((c) => c.name === ui.profileColumn) && (
          <ProfilePanel
            nodeId={previewId}
            hash={previewAnalysis.hash}
            column={ui.profileColumn}
            onClose={() => ui.setProfileColumn(null)}
          />
        )}
      </div>
    );
  }

  return (
    <section className="flex h-full min-h-0 flex-col bg-card" aria-label={t.preview.title}>
      {header}
      <div className="min-h-0 flex-1">{body}</div>
      {menu && (
        <ColumnMenu
          state={menu}
          onClose={() => setMenu(null)}
          onRename={(c) => setRenaming(c)}
          onProfile={(c) => ui.setProfileColumn(c)}
        />
      )}
      <RenameDialog column={renaming} onClose={() => setRenaming(null)} />
    </section>
  );
}

function ColumnMenu({
  state,
  onClose,
  onRename,
  onProfile,
}: {
  state: MenuState;
  onClose: () => void;
  onRename: (c: string) => void;
  onProfile: (c: string) => void;
}) {
  const { column: c, bounds } = state;
  const m = t.preview.columnMenu;
  const go = (fn: () => void) => () => {
    fn();
    onClose();
  };
  return (
    <DropdownMenu open onOpenChange={(o) => !o && onClose()}>
      <DropdownMenuTrigger asChild>
        <span
          className="pointer-events-none fixed"
          style={{ left: bounds.x, top: bounds.y + bounds.height, width: bounds.width, height: 1 }}
        />
      </DropdownMenuTrigger>
      <DropdownMenuContent align="start" className="w-56">
        <DropdownMenuLabel>{c.name}</DropdownMenuLabel>
        {state.value && (
          <>
            <DropdownMenuItem
              onSelect={go(() =>
                actions.filterByValue(
                  c.name,
                  state.value?.v == null ? null : filterValue(state.value.v, c.type),
                ),
              )}
            >
              <Filter /> {m.filterValue}
            </DropdownMenuItem>
            <DropdownMenuSeparator />
          </>
        )}
        <DropdownMenuItem onSelect={go(() => onProfile(c.name))}>
          <BarChart3 /> {m.profile}
        </DropdownMenuItem>
        <DropdownMenuItem onSelect={go(() => actions.sortBy(c.name, "asc"))}>
          <SortAsc /> {m.sortAsc}
        </DropdownMenuItem>
        <DropdownMenuItem onSelect={go(() => actions.sortBy(c.name, "desc"))}>
          <SortDesc /> {m.sortDesc}
        </DropdownMenuItem>
        <DropdownMenuItem onSelect={go(() => actions.groupBy(c.name))}>
          <Group /> {m.groupBy}
        </DropdownMenuItem>
        <DropdownMenuItem onSelect={go(() => actions.newColumnFrom(c.name))}>
          <Sigma /> {m.newFrom}
        </DropdownMenuItem>
        <DropdownMenuSeparator />
        <DropdownMenuItem onSelect={go(() => onRename(c.name))}>
          <Pencil /> {m.rename}
        </DropdownMenuItem>
        <DropdownMenuItem onSelect={go(() => actions.removeColumn(c.name))}>
          <Trash2 /> {m.remove}
        </DropdownMenuItem>
        <DropdownMenuItem onSelect={go(() => void navigator.clipboard?.writeText(c.name))}>
          <Copy /> {t.common.copy}
        </DropdownMenuItem>
        <DropdownMenuSeparator />
        <DropdownMenuLabel>
          <span className="inline-flex items-center gap-1">
            <Shapes className="size-3" /> {m.changeType}
          </span>
        </DropdownMenuLabel>
        <div className="grid grid-cols-2">
          {TYPE_OPTIONS.filter((o) => o.value !== c.type).map((o) => (
            <DropdownMenuItem key={o.value} onSelect={go(() => actions.changeType(c.name, c.type, o.value))}>
              {o.label}
            </DropdownMenuItem>
          ))}
        </div>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}

function RenameDialog({ column, onClose }: { column: string | null; onClose: () => void }) {
  const [value, setValue] = useState("");
  useEffect(() => setValue(column ?? ""), [column]);
  const submit = () => {
    if (column) actions.renameColumn(column, value.trim());
    onClose();
  };
  return (
    <Dialog
      open={column !== null}
      onOpenChange={(o) => !o && onClose()}
      title={`${t.preview.columnMenu.rename}: ${column ?? ""}`}
      footer={
        <>
          <Button variant="outline" onClick={onClose}>
            {t.common.cancel}
          </Button>
          <Button onClick={submit}>{t.common.confirm}</Button>
        </>
      }
    >
      <Input
        autoFocus
        value={value}
        onChange={(e) => setValue(e.target.value)}
        onKeyDown={(e) => e.key === "Enter" && submit()}
        aria-label={t.common.name}
      />
    </Dialog>
  );
}
