import { useReactFlow } from "@xyflow/react";
import { BookmarkPlus, Code2, Copy, Trash2 } from "lucide-react";
import { useState } from "react";

import { ApiError } from "@/api/client";
import { fetchSql } from "@/api/hooks";
import { IssueList } from "@/components/IssueList";
import { Badge, Button, Dialog, Tooltip } from "@/components/ui";
import { NodePanel } from "@/features/nodes/panels";
import { getMeta } from "@/features/nodes/registry";
import { CATEGORY_COLOR } from "@/features/nodes/types";
import { SaveTemplateDialog } from "@/features/templates/SaveTemplateDialog";
import { t } from "@/i18n/pt-BR";
import { usePipelineStore } from "@/stores/pipelineStore";

import { useNodeAnalysis, useServerPipeline } from "./analysis";
import { InputsEditor } from "./InputsEditor";

function SqlDialog({ nodeId, open, onClose }: { nodeId: string; open: boolean; onClose: () => void }) {
  const pipeline = useServerPipeline((s) => s.pipeline);
  const [sql, setSql] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);
  return (
    <Dialog
      open={open}
      onOpenChange={(o) => {
        if (!o) {
          onClose();
          return;
        }
        setSql(null);
        setError(null);
        fetchSql(pipeline, nodeId)
          .then(setSql)
          .catch((e: unknown) => setError(e instanceof ApiError ? e.message : String(e)));
      }}
      title={t.editor.copyAsSql}
      className="w-[min(760px,calc(100vw-32px))]"
      footer={
        <Button
          disabled={!sql}
          onClick={() => {
            if (sql) void navigator.clipboard.writeText(sql).then(() => setCopied(true));
          }}
        >
          <Copy /> {copied ? t.common.copied : t.common.copy}
        </Button>
      }
    >
      {error && <p className="text-danger">{error}</p>}
      <pre className="max-h-[60vh] overflow-auto rounded-md bg-muted p-3 font-mono text-[11px]">
        {sql ?? t.common.loading}
      </pre>
    </Dialog>
  );
}

export function ConfigSidebar() {
  const node = usePipelineStore((s) => s.pipeline.nodes.find((n) => n.id === s.selectedId));
  const analysis = useNodeAnalysis(node?.id);
  const [sqlOpen, setSqlOpen] = useState(false);
  const [templateIds, setTemplateIds] = useState<string[] | null>(null);
  const rf = useReactFlow();
  if (!node) {
    return (
      <aside className="flex h-full w-80 shrink-0 items-center justify-center border-l bg-background p-6 text-center text-xs text-muted-foreground">
        {t.editor.selectNode}
      </aside>
    );
  }
  const meta = getMeta(node.type);
  const store = usePipelineStore.getState();
  const columns = analysis?.input_columns.in ?? analysis?.input_columns.left ?? [];
  const issues = analysis?.issues ?? [];
  const Icon = meta?.icon;
  const color = meta ? CATEGORY_COLOR[meta.category] : undefined;

  return (
    <aside
      className="flex h-full w-80 shrink-0 flex-col border-l bg-background"
      aria-label="Configuração do nó"
    >
      <div className="flex items-center gap-2 border-b px-3 py-2">
        {Icon && <Icon className="size-4 shrink-0" style={{ color }} />}
        <input
          key={node.id}
          defaultValue={node.ui.label ?? ""}
          placeholder={meta?.label}
          onBlur={(e) => store.setLabel(node.id, e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && (e.target as HTMLInputElement).blur()}
          className="min-w-0 flex-1 rounded bg-transparent px-1 text-[14px] font-semibold outline-none hover:bg-muted focus:bg-muted"
          aria-label={t.common.rename}
        />
        {analysis && analysis.status !== "ok" && (
          <Badge
            tone={
              analysis.status === "error" ? "danger" : analysis.status === "warning" ? "warning" : "neutral"
            }
          >
            {t.status[analysis.status]}
          </Badge>
        )}
      </div>
      <div className="flex items-center gap-1 border-b px-2 py-1">
        <span className="flex-1 truncate px-1 text-[11px] text-muted-foreground">{meta?.description}</span>
        {meta?.hasOutput && !meta.annotation && (
          <Tooltip content={t.editor.copyAsSql}>
            <Button
              variant="ghost"
              size="iconSm"
              onClick={() => setSqlOpen(true)}
              aria-label={t.editor.copyAsSql}
            >
              <Code2 />
            </Button>
          </Tooltip>
        )}
        {!meta?.annotation && (
          <Tooltip content={t.templates.save}>
            <Button
              variant="ghost"
              size="iconSm"
              onClick={() => {
                const selected = rf
                  .getNodes()
                  .filter((n) => n.selected)
                  .map((n) => n.id);
                setTemplateIds(selected.includes(node.id) ? selected : [node.id]);
              }}
              aria-label={t.templates.save}
            >
              <BookmarkPlus />
            </Button>
          </Tooltip>
        )}
        <Tooltip content={t.editor.duplicate}>
          <Button
            variant="ghost"
            size="iconSm"
            onClick={() => store.duplicate([node.id])}
            aria-label={t.editor.duplicate}
          >
            <Copy />
          </Button>
        </Tooltip>
        <Tooltip content={t.editor.deleteNode}>
          <Button
            variant="ghost"
            size="iconSm"
            onClick={() => store.removeNodes([node.id])}
            aria-label={t.editor.deleteNode}
          >
            <Trash2 />
          </Button>
        </Tooltip>
      </div>
      <div className="flex min-h-0 flex-1 flex-col gap-3 overflow-auto p-3">
        {issues.length > 0 && <IssueList issues={issues} />}
        {
          <NodePanel
            type={node.type}
            key={node.id}
            node={node}
            config={node.config}
            columns={columns}
            update={(next) => store.updateConfig(node.id, next)}
          />
        }
        <InputsEditor node={node} />
      </div>
      <SqlDialog nodeId={node.id} open={sqlOpen} onClose={() => setSqlOpen(false)} />
      {templateIds && <SaveTemplateDialog nodeIds={templateIds} open onClose={() => setTemplateIds(null)} />}
    </aside>
  );
}
