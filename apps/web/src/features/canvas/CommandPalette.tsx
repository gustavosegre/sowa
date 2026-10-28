import { useReactFlow } from "@xyflow/react";
import {
  Columns3,
  CornerDownLeft,
  LayoutGrid,
  Maximize,
  Moon,
  Plus,
  Redo2,
  Undo2,
  Upload,
} from "lucide-react";
import { Dialog as DialogPrimitive } from "radix-ui";
import { useMemo, useState, type ReactNode } from "react";

import { Kbd } from "@/components/ui";
import { useAnalysis } from "@/features/editor/analysis";
import { allMetas, getMeta } from "@/features/nodes/registry";
import { CATEGORY_COLOR } from "@/features/nodes/types";
import { t } from "@/i18n/pt-BR";
import { cn } from "@/lib/utils";
import { redo, undo, usePipelineStore } from "@/stores/pipelineStore";
import { useUiStore } from "@/stores/uiStore";

interface Command {
  id: string;
  group: string;
  label: string;
  hint?: string;
  icon: ReactNode;
  run: () => void;
}

function norm(s: string): string {
  return s.normalize("NFKD").replace(/[̀-ͯ]/g, "").toLowerCase();
}

/** Ctrl+K: add a node, find a node or a column, run an action. */
export function CommandPalette({ onAutoLayout }: { onAutoLayout: () => void }) {
  const open = useUiStore((s) => s.paletteOpen);
  const setOpen = useUiStore((s) => s.setPaletteOpen);
  const nodes = usePipelineStore((s) => s.pipeline.nodes);
  const { data: analysis } = useAnalysis();
  const rf = useReactFlow();
  const [q, setQ] = useState("");
  const [active, setActive] = useState(0);

  const commands = useMemo<Command[]>(() => {
    const out: Command[] = [];
    const focus = (id: string) => {
      usePipelineStore.getState().select(id);
      const n = nodes.find((x) => x.id === id);
      if (n) void rf.setCenter(n.ui.x + 120, n.ui.y + 40, { zoom: 1, duration: 300 });
    };
    for (const m of allMetas()) {
      if (m.type === "source") continue;
      const Icon = m.icon;
      out.push({
        id: `add:${m.type}`,
        group: t.palette.addNode,
        label: m.label,
        hint: m.description,
        icon: <Icon className="size-3.5" style={{ color: CATEGORY_COLOR[m.category] }} />,
        run: () => {
          const st = usePipelineStore.getState();
          st.addNode(m.type, st.selectedId ? { connectFrom: st.selectedId } : {});
        },
      });
    }
    for (const n of nodes) {
      const meta = getMeta(n.type);
      const Icon = meta?.icon ?? Plus;
      out.push({
        id: `go:${n.id}`,
        group: t.palette.goToNode,
        label: n.ui.label || meta?.label || n.type,
        hint: meta?.label,
        icon: <Icon className="size-3.5 text-muted-foreground" />,
        run: () => focus(n.id),
      });
      for (const c of analysis?.nodes[n.id]?.changed_columns ?? []) {
        out.push({
          id: `col:${n.id}:${c}`,
          group: t.palette.columns,
          label: c,
          hint: `criada/alterada em ${n.ui.label || meta?.label || n.type}`,
          icon: <Columns3 className="size-3.5 text-muted-foreground" />,
          run: () => focus(n.id),
        });
      }
      if (n.type === "source") {
        for (const c of analysis?.nodes[n.id]?.columns ?? []) {
          out.push({
            id: `col:${n.id}:${c.name}`,
            group: t.palette.columns,
            label: c.name,
            hint: `fonte ${n.ui.label || "Fonte"}`,
            icon: <Columns3 className="size-3.5 text-muted-foreground" />,
            run: () => focus(n.id),
          });
        }
      }
    }
    const ui = useUiStore.getState();
    out.push(
      {
        id: "a:import",
        group: t.palette.actions,
        label: t.editor.upload,
        icon: <Upload className="size-3.5" />,
        run: () => ui.openWizard(),
      },
      {
        id: "a:layout",
        group: t.palette.actions,
        label: t.editor.autoLayout,
        icon: <LayoutGrid className="size-3.5" />,
        run: onAutoLayout,
      },
      {
        id: "a:fit",
        group: t.palette.actions,
        label: t.editor.fitView,
        icon: <Maximize className="size-3.5" />,
        run: () => void rf.fitView({ duration: 300 }),
      },
      {
        id: "a:undo",
        group: t.palette.actions,
        label: t.editor.undo,
        icon: <Undo2 className="size-3.5" />,
        run: undo,
      },
      {
        id: "a:redo",
        group: t.palette.actions,
        label: t.editor.redo,
        icon: <Redo2 className="size-3.5" />,
        run: redo,
      },
      {
        id: "a:theme",
        group: t.palette.actions,
        label: t.editor.theme,
        icon: <Moon className="size-3.5" />,
        run: ui.toggleTheme,
      },
    );
    return out;
  }, [nodes, analysis, rf, onAutoLayout]);

  const s = norm(q.trim());
  const filtered = (
    s ? commands.filter((c) => norm(`${c.label} ${c.hint ?? ""} ${c.group}`).includes(s)) : commands
  ).slice(0, 60);

  const run = (c: Command | undefined) => {
    if (!c) return;
    setOpen(false);
    setQ("");
    c.run();
  };

  let lastGroup = "";
  return (
    <DialogPrimitive.Root open={open} onOpenChange={(o) => (setOpen(o), setQ(""), setActive(0))}>
      <DialogPrimitive.Portal>
        <DialogPrimitive.Overlay className="fixed inset-0 z-50 bg-black/30" />
        <DialogPrimitive.Content
          className="fixed left-1/2 top-[15vh] z-50 w-[min(560px,calc(100vw-32px))] -translate-x-1/2 overflow-hidden rounded-lg border bg-card shadow-2xl outline-none"
          aria-describedby={undefined}
        >
          <DialogPrimitive.Title className="sr-only">{t.editor.commandPalette}</DialogPrimitive.Title>
          <input
            autoFocus
            value={q}
            onChange={(e) => (setQ(e.target.value), setActive(0))}
            placeholder={t.palette.placeholder}
            className="h-11 w-full border-b bg-transparent px-4 text-[14px] outline-none"
            onKeyDown={(e) => {
              if (e.key === "ArrowDown") {
                e.preventDefault();
                setActive((a) => Math.min(a + 1, filtered.length - 1));
              } else if (e.key === "ArrowUp") {
                e.preventDefault();
                setActive((a) => Math.max(a - 1, 0));
              } else if (e.key === "Enter") run(filtered[active]);
            }}
            role="combobox"
            aria-expanded
            aria-controls="palette-list"
          />
          <ul id="palette-list" role="listbox" className="max-h-[50vh] overflow-auto p-1">
            {filtered.map((c, i) => {
              const header = c.group !== lastGroup ? c.group : null;
              lastGroup = c.group;
              return (
                <li key={c.id}>
                  {header && (
                    <p className="px-2 pb-0.5 pt-2 text-[10px] font-semibold uppercase tracking-wide text-muted-foreground">
                      {header}
                    </p>
                  )}
                  <button
                    type="button"
                    role="option"
                    aria-selected={i === active}
                    onMouseEnter={() => setActive(i)}
                    onClick={() => run(c)}
                    className={cn(
                      "flex w-full items-center gap-2 rounded px-2 py-1.5 text-left text-[13px]",
                      i === active && "bg-muted",
                    )}
                  >
                    {c.icon}
                    <span className="truncate">{c.label}</span>
                    {c.hint && (
                      <span className="min-w-0 flex-1 truncate text-[11px] text-muted-foreground">
                        {c.hint}
                      </span>
                    )}
                    {i === active && <CornerDownLeft className="size-3 text-muted-foreground" />}
                  </button>
                </li>
              );
            })}
            {!filtered.length && (
              <li className="px-3 py-4 text-center text-xs text-muted-foreground">{t.palette.empty}</li>
            )}
          </ul>
          <div className="flex gap-3 border-t px-3 py-1.5 text-[10px] text-muted-foreground">
            <span>
              <Kbd>↑</Kbd> <Kbd>↓</Kbd> navegar
            </span>
            <span>
              <Kbd>Enter</Kbd> executar
            </span>
            <span>
              <Kbd>Esc</Kbd> fechar
            </span>
          </div>
        </DialogPrimitive.Content>
      </DialogPrimitive.Portal>
    </DialogPrimitive.Root>
  );
}
