import {
  Background,
  BackgroundVariant,
  Controls,
  MiniMap,
  ReactFlow,
  applyNodeChanges,
  useReactFlow,
  type Connection,
  type Edge,
  type EdgeChange,
  type Node,
  type NodeChange,
} from "@xyflow/react";
import { FileUp } from "lucide-react";
import { useCallback, useEffect, useMemo, useRef, useState, type DragEvent } from "react";

import { useSources } from "@/api/hooks";
import type { PipelineNode } from "@/api/types";
import { Button } from "@/components/ui";
import { useAnalysis } from "@/features/editor/analysis";
import { useProjectId } from "@/features/editor/project";
import { getMeta } from "@/features/nodes/registry";
import { CATEGORY_COLOR } from "@/features/nodes/types";
import { t } from "@/i18n/pt-BR";
import { usePipelineStore } from "@/stores/pipelineStore";
import { useUiStore } from "@/stores/uiStore";

import { FrameNode, NoteNode } from "./AnnotationNodes";
import { NodeCard, type CardData } from "./NodeCard";

const nodeTypes = { card: NodeCard, note: NoteNode, frame: FrameNode };

export const DND_NODE = "application/forja-node";
export const DND_SOURCE = "application/forja-source";

function rfType(n: PipelineNode): "card" | "note" | "frame" {
  return n.type === "note" ? "note" : n.type === "frame" ? "frame" : "card";
}

export function Canvas() {
  const pipeline = usePipelineStore((s) => s.pipeline);
  const selectedId = usePipelineStore((s) => s.selectedId);
  const { data: analysis } = useAnalysis();
  const projectId = useProjectId();
  const { data: sources } = useSources(projectId);
  const openWizard = useUiStore((s) => s.openWizard);
  const rf = useReactFlow();
  const dragging = useRef<Record<string, { x: number; y: number }>>({});
  const [rfNodes, setRfNodes] = useState<Node[]>([]);
  const [selectedEdges, setSelectedEdges] = useState<Set<string>>(new Set());
  const [fileOver, setFileOver] = useState(false);

  const sourceNames = useMemo(() => new Map((sources ?? []).map((s) => [s.id, s.name])), [sources]);

  // Derive React Flow nodes from the store; keep in-flight drag positions and multi-selection.
  const lastSelected = useRef<string | null>(null);
  useEffect(() => {
    // A selection made through the store (new node, palette…) replaces the canvas selection.
    const selectionChanged = lastSelected.current !== selectedId;
    lastSelected.current = selectedId;
    setRfNodes((prev) => {
      const prevById = new Map(prev.map((n) => [n.id, n]));
      return pipeline.nodes.map((n): Node => {
        const old = prevById.get(n.id);
        const type = rfType(n);
        const isFrame = type === "frame";
        const data: CardData = {
          node: n,
          analysis: analysis?.nodes[n.id],
          sourceName:
            n.type === "source"
              ? sourceNames.get(typeof n.config.source_id === "string" ? n.config.source_id : "")
              : undefined,
        };
        return {
          id: n.id,
          type,
          position: dragging.current[n.id] ?? { x: n.ui.x, y: n.ui.y },
          data,
          selected: selectionChanged || !old ? n.id === selectedId : Boolean(old.selected),
          zIndex: isFrame ? -1 : undefined,
          ...(isFrame ? { style: { width: n.ui.width ?? 480, height: n.ui.height ?? 300 } } : {}),
          ...(old?.measured ? { measured: old.measured } : {}),
        };
      });
    });
  }, [pipeline.nodes, analysis, sourceNames, selectedId]);

  const edges = useMemo<Edge[]>(
    () =>
      pipeline.edges.map((e) => {
        const target = analysis?.nodes[e.target];
        const src = pipeline.nodes.find((n) => n.id === e.source);
        const meta = src ? getMeta(src.type) : undefined;
        return {
          id: e.id,
          source: e.source,
          target: e.target,
          sourceHandle: e.source_handle,
          targetHandle: e.target_handle,
          selected: selectedEdges.has(e.id),
          animated: target?.status === "blocked",
          style: meta
            ? { stroke: `color-mix(in oklch, ${CATEGORY_COLOR[meta.category]} 70%, var(--muted-foreground))` }
            : undefined,
        };
      }),
    [pipeline.edges, pipeline.nodes, analysis, selectedEdges],
  );

  // Bring a newly selected node into view (e.g. added off-screen to the right).
  useEffect(() => {
    if (!selectedId) return;
    const n = pipeline.nodes.find((x) => x.id === selectedId);
    const el = document.querySelector(".react-flow");
    if (!n || !el) return;
    const { x, y, zoom } = rf.getViewport();
    const rect = el.getBoundingClientRect();
    const sx = n.ui.x * zoom + x;
    const sy = n.ui.y * zoom + y;
    const outside = sx < 0 || sy < 0 || sx + 250 * zoom > rect.width || sy + 100 * zoom > rect.height;
    if (outside) void rf.setCenter(n.ui.x + 125, n.ui.y + 50, { zoom, duration: 250 });
    // Only when the selection changes, not on every edit of the selected node.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedId]);

  const onNodesChange = useCallback((changes: NodeChange[]) => {
    const store = usePipelineStore.getState();
    const removed = changes.filter((c) => c.type === "remove").map((c) => c.id);
    if (removed.length) store.removeNodes(removed);
    for (const c of changes) {
      if (c.type === "position" && c.dragging && c.position) dragging.current[c.id] = c.position;
      if (c.type === "select" && c.selected) store.select(c.id);
    }
    setRfNodes((nds) =>
      applyNodeChanges(
        changes.filter((c) => c.type !== "remove"),
        nds,
      ),
    );
  }, []);

  const onNodeDragStop = useCallback((_: unknown, __: Node, nodes: Node[]) => {
    const positions: Record<string, { x: number; y: number }> = {};
    for (const n of nodes) positions[n.id] = n.position;
    dragging.current = {};
    usePipelineStore.getState().movePositions(positions);
  }, []);

  const onEdgesChange = useCallback((changes: EdgeChange[]) => {
    const removed = changes.filter((c) => c.type === "remove").map((c) => c.id);
    if (removed.length) usePipelineStore.getState().removeEdges(removed);
    setSelectedEdges((prev) => {
      const next = new Set(prev);
      for (const c of changes) {
        if (c.type === "select") {
          if (c.selected) next.add(c.id);
          else next.delete(c.id);
        }
      }
      return next;
    });
  }, []);

  const onConnect = useCallback((c: Connection) => {
    if (c.source && c.target) usePipelineStore.getState().connect(c.source, c.target, c.targetHandle ?? "in");
  }, []);

  const isValidConnection = useCallback(
    (c: Connection | Edge) => c.source !== c.target && c.targetHandle !== null,
    [],
  );

  const onDragOver = (e: DragEvent) => {
    e.preventDefault();
    const types = e.dataTransfer.types;
    e.dataTransfer.dropEffect = types.includes("Files") ? "copy" : "move";
    if (types.includes("Files")) setFileOver(true);
  };

  const onDrop = (e: DragEvent) => {
    e.preventDefault();
    setFileOver(false);
    const file = e.dataTransfer.files[0];
    if (file) {
      openWizard({ file });
      return;
    }
    const position = rf.screenToFlowPosition({ x: e.clientX, y: e.clientY });
    const store = usePipelineStore.getState();
    const sourceId = e.dataTransfer.getData(DND_SOURCE);
    if (sourceId) {
      store.addNode("source", { position, config: { source_id: sourceId } });
      return;
    }
    const type = e.dataTransfer.getData(DND_NODE);
    if (!type) return;
    // Dropped over an edge: insert the node in the middle of it.
    const edgeEl = document
      .elementsFromPoint(e.clientX, e.clientY)
      .find((el) => el.getAttribute("data-testid")?.startsWith("rf__edge-"));
    const edgeId = edgeEl?.getAttribute("data-testid")?.slice("rf__edge-".length);
    const meta = getMeta(type);
    if (edgeId && meta && meta.inputs.length > 0 && meta.hasOutput) {
      store.insertOnEdge(edgeId, type, position);
      return;
    }
    store.addNode(type, { position });
  };

  const empty = pipeline.nodes.length === 0;

  return (
    <div className="relative h-full w-full" onDragLeave={() => setFileOver(false)}>
      <ReactFlow
        nodes={rfNodes}
        edges={edges}
        nodeTypes={nodeTypes}
        onNodesChange={onNodesChange}
        onEdgesChange={onEdgesChange}
        onNodeDragStop={onNodeDragStop}
        onConnect={onConnect}
        isValidConnection={isValidConnection}
        onPaneClick={() => usePipelineStore.getState().select(null)}
        onDragOver={onDragOver}
        onDrop={onDrop}
        deleteKeyCode={["Delete", "Backspace"]}
        multiSelectionKeyCode="Shift"
        snapToGrid
        snapGrid={[8, 8]}
        fitView
        fitViewOptions={{ maxZoom: 1, padding: 0.2 }}
        minZoom={0.15}
        proOptions={{ hideAttribution: true }}
        defaultEdgeOptions={{ type: "smoothstep" }}
        aria-label="Canvas do fluxo"
      >
        <Background variant={BackgroundVariant.Dots} gap={16} size={1.2} />
        <Controls showInteractive={false} position="bottom-left" />
        <MiniMap
          pannable
          zoomable
          position="bottom-right"
          nodeColor={(n) => {
            const pn = (n.data as CardData | undefined)?.node;
            const meta = pn ? getMeta(pn.type) : undefined;
            return meta ? CATEGORY_COLOR[meta.category] : "var(--muted-foreground)";
          }}
          className="!h-24 !w-36 rounded border"
        />
      </ReactFlow>
      {empty && (
        <div className="pointer-events-none absolute inset-0 flex items-center justify-center">
          <div className="pointer-events-auto flex max-w-sm flex-col items-center gap-3 rounded-xl border bg-card/90 p-6 text-center shadow-sm backdrop-blur">
            <FileUp className="size-8 text-primary" />
            <h2 className="text-[15px] font-semibold">{t.editor.emptyCanvasTitle}</h2>
            <p className="text-xs text-muted-foreground">{t.editor.emptyCanvasBody}</p>
            <Button onClick={() => openWizard()}>
              <FileUp /> {t.editor.upload}
            </Button>
          </div>
        </div>
      )}
      {fileOver && (
        <div className="pointer-events-none absolute inset-3 flex items-center justify-center rounded-xl border-2 border-dashed border-primary bg-primary/5 text-sm font-medium text-primary">
          {t.editor.dropHere}
        </div>
      )}
    </div>
  );
}
