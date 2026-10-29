import { ReactFlowProvider, useReactFlow } from "@xyflow/react";
import {
  ArrowLeft,
  Braces,
  Check,
  CircleAlert,
  Command,
  History,
  LayoutGrid,
  Maximize,
  Moon,
  Redo2,
  Sun,
  Undo2,
} from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";
import { useStore } from "zustand";

import { loadPipeline, savePipeline, useProject, useRenameProject } from "@/api/hooks";
import { SignOutButton } from "@/app/SignOutButton";
import { Button, Select, Spinner, Tooltip } from "@/components/ui";
import { Canvas } from "@/features/canvas/Canvas";
import { CommandPalette } from "@/features/canvas/CommandPalette";
import { autoLayout } from "@/features/canvas/layout";
import { Library } from "@/features/canvas/Library";
import { PreviewPanel } from "@/features/preview/PreviewPanel";
import { ImportWizard } from "@/features/sources/ImportWizard";
import { t } from "@/i18n/pt-BR";
import { cn } from "@/lib/utils";
import { redo, undo, usePipelineStore, type ClipboardPayload } from "@/stores/pipelineStore";
import { useUiStore } from "@/stores/uiStore";

import { useSyncServerPipeline } from "./analysis";
import { ConfigSidebar } from "./ConfigSidebar";
import { ParamsDialog } from "./ParamsDialog";
import { VersionsDialog } from "./VersionsDialog";
import { switchLocale } from "./locale";
import { ProjectContext } from "./project";

const CLIP_KEY = "sowa-clipboard";

function isTyping(e: KeyboardEvent): boolean {
  const el = e.target as HTMLElement | null;
  return Boolean(el?.closest("input, textarea, select, [contenteditable=true], .cm-editor"));
}

function useAutosave(projectId: string, loaded: boolean) {
  const setStatus = useUiStore((s) => s.setSaveStatus);
  useEffect(() => {
    if (!loaded) return;
    let timer: ReturnType<typeof setTimeout> | undefined;
    const unsub = usePipelineStore.subscribe((s, prev) => {
      if (s.pipeline === prev.pipeline) return;
      setStatus("dirty");
      if (timer) clearTimeout(timer);
      timer = setTimeout(() => {
        setStatus("saving");
        savePipeline(projectId, usePipelineStore.getState().pipeline)
          .then(() => setStatus(usePipelineStore.getState().pipeline === s.pipeline ? "saved" : "dirty"))
          .catch(() => setStatus("error"));
      }, 1000);
    });
    return () => {
      unsub();
      if (timer) clearTimeout(timer);
    };
  }, [projectId, loaded, setStatus]);
}

function SaveIndicator() {
  const status = useUiStore((s) => s.saveStatus);
  const label = {
    saved: t.editor.saved,
    saving: t.editor.saving,
    dirty: t.editor.unsaved,
    error: t.editor.saveError,
  }[status];
  return (
    <span
      className={cn(
        "flex items-center gap-1 text-[11px]",
        status === "error" ? "text-danger" : "text-muted-foreground",
      )}
      role="status"
      data-testid="save-status"
    >
      {status === "saved" && <Check className="size-3" />}
      {status === "saving" && <Spinner className="size-3" />}
      {status === "error" && <CircleAlert className="size-3" />}
      {label}
    </span>
  );
}

function ProjectName({ projectId }: { projectId: string }) {
  const { data } = useProject(projectId);
  const rename = useRenameProject();
  if (!data) return null;
  return (
    <input
      key={data.name}
      defaultValue={data.name}
      onBlur={(e) =>
        e.target.value.trim() &&
        e.target.value !== data.name &&
        rename.mutate({ id: projectId, name: e.target.value })
      }
      onKeyDown={(e) => e.key === "Enter" && (e.target as HTMLInputElement).blur()}
      className="w-56 rounded bg-transparent px-1.5 py-0.5 text-[14px] font-semibold outline-none hover:bg-muted focus:bg-muted"
      aria-label="Nome do projeto"
    />
  );
}

function Toolbar({
  projectId,
  onBack,
  onAutoLayout,
}: {
  projectId: string;
  onBack: () => void;
  onAutoLayout: () => void;
}) {
  const rf = useReactFlow();
  const ui = useUiStore();
  const locale = usePipelineStore((s) => s.pipeline.settings.locale);
  const temporal = useStore(usePipelineStore.temporal);
  const params = usePipelineStore((s) => s.pipeline.settings.params.length);
  const [paramsOpen, setParamsOpen] = useState(false);
  const [versionsOpen, setVersionsOpen] = useState(false);
  return (
    <header className="flex h-11 shrink-0 items-center gap-2 border-b bg-background px-2">
      <Tooltip content={t.projects.title}>
        <Button variant="ghost" size="icon" onClick={onBack} aria-label={t.projects.title}>
          <ArrowLeft />
        </Button>
      </Tooltip>
      <span className="flex size-6 items-center justify-center rounded-md bg-primary text-[12px] font-bold text-primary-foreground">
        F
      </span>
      <ProjectName projectId={projectId} />
      <SaveIndicator />
      <span className="flex-1" />
      <Tooltip content={t.editor.undo}>
        <Button
          variant="ghost"
          size="icon"
          onClick={undo}
          disabled={!temporal.pastStates.length}
          aria-label={t.editor.undo}
        >
          <Undo2 />
        </Button>
      </Tooltip>
      <Tooltip content={t.editor.redo}>
        <Button
          variant="ghost"
          size="icon"
          onClick={redo}
          disabled={!temporal.futureStates.length}
          aria-label={t.editor.redo}
        >
          <Redo2 />
        </Button>
      </Tooltip>
      <div className="mx-1 h-5 w-px bg-border" />
      <Tooltip content={t.editor.autoLayout}>
        <Button variant="ghost" size="icon" onClick={onAutoLayout} aria-label={t.editor.autoLayout}>
          <LayoutGrid />
        </Button>
      </Tooltip>
      <Tooltip content={t.editor.fitView}>
        <Button
          variant="ghost"
          size="icon"
          onClick={() => void rf.fitView({ duration: 300, maxZoom: 1 })}
          aria-label={t.editor.fitView}
        >
          <Maximize />
        </Button>
      </Tooltip>
      <Button variant="ghost" size="sm" onClick={() => setParamsOpen(true)} aria-label={t.params.button}>
        <Braces /> {t.params.button}
        {params > 0 && <span className="rounded bg-muted px-1 text-[10px]">{params}</span>}
      </Button>
      <Button variant="ghost" size="sm" onClick={() => setVersionsOpen(true)} aria-label={t.versions.button}>
        <History /> {t.versions.button}
      </Button>
      <ParamsDialog open={paramsOpen} onClose={() => setParamsOpen(false)} />
      <VersionsDialog projectId={projectId} open={versionsOpen} onClose={() => setVersionsOpen(false)} />
      <Tooltip content={t.editor.locale}>
        <Select
          className="w-36"
          value={locale}
          options={[
            { value: "pt-BR", label: t.editor.localePt },
            { value: "en-US", label: t.editor.localeEn },
          ]}
          onChange={(v) => void switchLocale(usePipelineStore.getState().pipeline, v)}
          aria-label={t.editor.locale}
        />
      </Tooltip>
      <Button
        variant="outline"
        size="sm"
        onClick={() => ui.setPaletteOpen(true)}
        aria-label={t.editor.commandPalette}
      >
        <Command /> Ctrl+K
      </Button>
      <Tooltip content={t.editor.theme}>
        <Button variant="ghost" size="icon" onClick={ui.toggleTheme} aria-label={t.editor.theme}>
          {ui.theme === "dark" ? <Sun /> : <Moon />}
        </Button>
      </Tooltip>
      <SignOutButton />
    </header>
  );
}

function PreviewResizer() {
  const setHeight = useUiStore((s) => s.setPreviewHeight);
  const collapsed = useUiStore((s) => s.previewCollapsed);
  if (collapsed) return null;
  return (
    <div
      role="separator"
      aria-orientation="horizontal"
      aria-label="Redimensionar prévia"
      tabIndex={0}
      className="h-1.5 shrink-0 cursor-row-resize border-t bg-background hover:bg-primary/30"
      onPointerDown={(e) => {
        const startY = e.clientY;
        const start = useUiStore.getState().previewHeight;
        const move = (ev: PointerEvent) => setHeight(start + (startY - ev.clientY));
        const up = () => {
          window.removeEventListener("pointermove", move);
          window.removeEventListener("pointerup", up);
        };
        window.addEventListener("pointermove", move);
        window.addEventListener("pointerup", up);
      }}
      onKeyDown={(e) => {
        const h = useUiStore.getState().previewHeight;
        if (e.key === "ArrowUp") setHeight(h + 24);
        if (e.key === "ArrowDown") setHeight(h - 24);
      }}
    />
  );
}

function EditorInner({ projectId, onBack }: { projectId: string; onBack: () => void }) {
  const [loaded, setLoaded] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const rf = useReactFlow();
  const previewHeight = useUiStore((s) => s.previewHeight);
  const previewCollapsed = useUiStore((s) => s.previewCollapsed);
  const theme = useUiStore((s) => s.theme);
  const didFit = useRef(false);
  useSyncServerPipeline();
  useAutosave(projectId, loaded);

  useEffect(() => {
    let alive = true;
    setLoaded(false);
    loadPipeline(projectId)
      .then((saved) => {
        if (!alive) return;
        usePipelineStore.getState().load(saved.pipeline);
        useUiStore.getState().setSaveStatus("saved");
        setLoaded(true);
      })
      .catch((e: unknown) => setError(e instanceof Error ? e.message : String(e)));
    return () => {
      alive = false;
    };
  }, [projectId]);

  useEffect(() => {
    if (loaded && !didFit.current) {
      didFit.current = true;
      setTimeout(() => void rf.fitView({ maxZoom: 1, padding: 0.2 }), 50);
    }
  }, [loaded, rf]);

  const onAutoLayout = useCallback(() => {
    const p = usePipelineStore.getState().pipeline;
    const sizes: Record<string, { width: number; height: number }> = {};
    for (const n of rf.getNodes())
      sizes[n.id] = { width: n.measured?.width ?? 240, height: n.measured?.height ?? 90 };
    void autoLayout(p, sizes).then((pos) => {
      usePipelineStore.getState().movePositions(pos);
      setTimeout(() => void rf.fitView({ duration: 300, maxZoom: 1 }), 50);
    });
  }, [rf]);

  // Keyboard shortcuts (CLAUDE.md §14).
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const mod = e.ctrlKey || e.metaKey;
      if (mod && e.key.toLowerCase() === "k") {
        e.preventDefault();
        useUiStore.getState().setPaletteOpen(true);
        return;
      }
      if (isTyping(e) || !mod) return;
      const key = e.key.toLowerCase();
      const store = usePipelineStore.getState();
      const selected = rf
        .getNodes()
        .filter((n) => n.selected)
        .map((n) => n.id);
      if (key === "z" && !e.shiftKey) {
        e.preventDefault();
        undo();
      } else if ((key === "z" && e.shiftKey) || key === "y") {
        e.preventDefault();
        redo();
      } else if (key === "d" && selected.length) {
        e.preventDefault();
        store.duplicate(selected);
      } else if (key === "c" && selected.length) {
        const ids = new Set(selected);
        const payload: ClipboardPayload = {
          kind: "sowa/nodes",
          nodes: store.pipeline.nodes.filter((n) => ids.has(n.id)),
          edges: store.pipeline.edges.filter((x) => ids.has(x.source) && ids.has(x.target)),
        };
        const text = JSON.stringify(payload);
        localStorage.setItem(CLIP_KEY, text);
        void navigator.clipboard?.writeText(text).catch(() => undefined);
      } else if (key === "v") {
        const paste = (text: string | null) => {
          if (!text) return;
          try {
            const payload = JSON.parse(text) as ClipboardPayload;
            if (payload.kind === "sowa/nodes") store.paste(payload, { x: 60, y: 60 });
          } catch {
            /* not ours */
          }
        };
        const fallback = () => paste(localStorage.getItem(CLIP_KEY));
        if (navigator.clipboard?.readText) navigator.clipboard.readText().then(paste, fallback);
        else fallback();
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [rf]);

  if (error) return <p className="p-6 text-danger">{error}</p>;
  if (!loaded) {
    return (
      <div className="flex h-full items-center justify-center">
        <Spinner className="size-6 text-primary" />
      </div>
    );
  }
  return (
    <div className={cn("flex h-full flex-col", theme === "dark" && "dark")}>
      <Toolbar projectId={projectId} onBack={onBack} onAutoLayout={onAutoLayout} />
      <div className="flex min-h-0 flex-1">
        <Library />
        <main className="flex min-w-0 flex-1 flex-col">
          <div className="min-h-0 flex-1">
            <Canvas />
          </div>
          <PreviewResizer />
          <div style={{ height: previewCollapsed ? undefined : previewHeight }} className="shrink-0">
            <PreviewPanel />
          </div>
        </main>
        <ConfigSidebar />
      </div>
      <ImportWizard />
      <CommandPalette onAutoLayout={onAutoLayout} />
    </div>
  );
}

export function Editor({ projectId, onBack }: { projectId: string; onBack: () => void }) {
  return (
    <ProjectContext.Provider value={projectId}>
      <ReactFlowProvider>
        <EditorInner projectId={projectId} onBack={onBack} />
      </ReactFlowProvider>
    </ProjectContext.Provider>
  );
}
