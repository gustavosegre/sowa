import { FileSpreadsheet, FileUp, Search, Trash2 } from "lucide-react";
import { useMemo, useState } from "react";

import { useDeleteSource, useSources } from "@/api/hooks";
import { Button, Spinner } from "@/components/ui";
import { useProjectId } from "@/features/editor/project";
import { allMetas } from "@/features/nodes/registry";
import { CATEGORY_COLOR, CATEGORY_ORDER } from "@/features/nodes/types";
import { t } from "@/i18n/pt-BR";
import { cn, fmtBytes, fmtInt } from "@/lib/utils";
import { usePipelineStore } from "@/stores/pipelineStore";
import { useUiStore } from "@/stores/uiStore";

import { DND_NODE, DND_SOURCE } from "./Canvas";

function norm(s: string): string {
  return s.normalize("NFKD").replace(/[̀-ͯ]/g, "").toLowerCase();
}

function NodeLibrary() {
  const [q, setQ] = useState("");
  const metas = useMemo(() => allMetas().filter((m) => m.type !== "source"), []);
  const s = norm(q.trim());
  const visible = s
    ? metas.filter((m) => norm(`${m.label} ${m.description} ${(m.keywords ?? []).join(" ")}`).includes(s))
    : metas;
  const add = (type: string) => {
    const st = usePipelineStore.getState();
    st.addNode(type, st.selectedId ? { connectFrom: st.selectedId } : {});
  };
  return (
    <div className="flex min-h-0 flex-1 flex-col">
      <div className="relative px-2 pb-2">
        <Search className="pointer-events-none absolute left-4 top-2 size-3.5 text-muted-foreground" />
        <input
          value={q}
          onChange={(e) => setQ(e.target.value)}
          placeholder={t.common.search}
          className="h-7 w-full rounded-md border bg-card pl-7 pr-2 text-[12px] outline-none focus-visible:ring-2 focus-visible:ring-ring/40"
          aria-label="Buscar nós"
        />
      </div>
      <div className="min-h-0 flex-1 overflow-auto px-2 pb-2">
        {CATEGORY_ORDER.map((cat) => {
          const items = visible.filter((m) => m.category === cat);
          if (!items.length) return null;
          return (
            <div key={cat} className="mb-2">
              <p className="px-1 pb-1 text-[10px] font-semibold uppercase tracking-wide text-muted-foreground">
                {t.categories[cat]}
              </p>
              {items.map((m) => {
                const Icon = m.icon;
                return (
                  <button
                    key={m.type}
                    type="button"
                    draggable
                    onDragStart={(e) => {
                      e.dataTransfer.setData(DND_NODE, m.type);
                      e.dataTransfer.effectAllowed = "move";
                    }}
                    onClick={() => add(m.type)}
                    className="group flex w-full cursor-grab items-center gap-2 rounded-md px-1.5 py-1 text-left hover:bg-muted active:cursor-grabbing"
                    title={m.description}
                  >
                    <span
                      className="flex size-5 shrink-0 items-center justify-center rounded"
                      style={{
                        background: `color-mix(in oklch, ${CATEGORY_COLOR[m.category]} 15%, transparent)`,
                      }}
                    >
                      <Icon className="size-3.5" style={{ color: CATEGORY_COLOR[m.category] }} />
                    </span>
                    <span className="truncate text-[12.5px]">{m.label}</span>
                  </button>
                );
              })}
            </div>
          );
        })}
      </div>
    </div>
  );
}

function SourcesLibrary() {
  const projectId = useProjectId();
  const { data: sources, isLoading } = useSources(projectId);
  const del = useDeleteSource();
  const openWizard = useUiStore((s) => s.openWizard);
  return (
    <div className="flex min-h-0 flex-1 flex-col gap-2 px-2 pb-2">
      <Button size="sm" variant="outline" onClick={() => openWizard()}>
        <FileUp /> {t.editor.upload}
      </Button>
      {isLoading && <Spinner />}
      <ul className="flex min-h-0 flex-1 flex-col gap-1 overflow-auto">
        {sources?.map((s) => (
          <li
            key={s.id}
            draggable={s.status === "ready"}
            onDragStart={(e) => {
              e.dataTransfer.setData(DND_SOURCE, s.id);
              e.dataTransfer.effectAllowed = "move";
            }}
            className={cn(
              "group flex items-start gap-2 rounded-md border bg-card px-2 py-1.5",
              s.status === "ready" ? "cursor-grab" : "opacity-60",
            )}
            title={s.status === "ready" ? "Arraste para o canvas" : "Importação não concluída"}
          >
            <FileSpreadsheet className="mt-0.5 size-3.5 shrink-0 text-cat-input" />
            <div className="min-w-0 flex-1">
              <p className="truncate text-[12.5px] font-medium">{s.name}</p>
              <p className="truncate text-[11px] text-muted-foreground">
                {s.status === "ready" ? `${fmtInt(s.row_count)} linhas · ` : "pendente · "}
                {fmtBytes(s.size_bytes)}
              </p>
            </div>
            <Button
              variant="ghost"
              size="iconSm"
              className="opacity-0 group-hover:opacity-100"
              aria-label={`${t.common.delete} ${s.name}`}
              onClick={() => {
                if (window.confirm(`Excluir o arquivo "${s.name}"? Nós Fonte que o usam ficarão com erro.`))
                  del.mutate(s.id);
              }}
            >
              <Trash2 />
            </Button>
          </li>
        ))}
      </ul>
    </div>
  );
}

export function Library() {
  const [tab, setTab] = useState<"nodes" | "sources">("nodes");
  return (
    <aside className="flex h-full w-56 shrink-0 flex-col border-r bg-background" aria-label="Biblioteca">
      <div className="flex gap-1 p-2" role="tablist">
        {(["nodes", "sources"] as const).map((k) => (
          <button
            key={k}
            type="button"
            role="tab"
            aria-selected={tab === k}
            onClick={() => setTab(k)}
            className={cn(
              "flex-1 cursor-pointer rounded-md px-2 py-1 text-[12px] font-medium",
              tab === k
                ? "bg-card shadow-sm ring-1 ring-border"
                : "text-muted-foreground hover:text-foreground",
            )}
          >
            {k === "nodes" ? t.editor.library : t.editor.sources}
          </button>
        ))}
      </div>
      {tab === "nodes" ? <NodeLibrary /> : <SourcesLibrary />}
    </aside>
  );
}
