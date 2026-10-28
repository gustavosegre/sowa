import { useQueryClient } from "@tanstack/react-query";
import { RotateCcw, Save } from "lucide-react";
import { useState } from "react";

import { errorIssue } from "@/api/client";
import { createVersion, restoreVersion, savePipeline, useVersions } from "@/api/hooks";
import { IssueItem } from "@/components/IssueList";
import { Badge, Button, Dialog, Input, Spinner } from "@/components/ui";
import { t } from "@/i18n/pt-BR";
import { fmtDateTime } from "@/lib/utils";
import { usePipelineStore } from "@/stores/pipelineStore";
import { useUiStore } from "@/stores/uiStore";

export function VersionsDialog({
  projectId,
  open,
  onClose,
}: {
  projectId: string;
  open: boolean;
  onClose: () => void;
}) {
  const qc = useQueryClient();
  const { data, isLoading } = useVersions(projectId, open);
  const [label, setLabel] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>(null);

  const run = async (fn: () => Promise<unknown>) => {
    setBusy(true);
    setError(null);
    try {
      // Pending edits go to the server first, so a version always matches what is on screen.
      await savePipeline(projectId, usePipelineStore.getState().pipeline);
      await fn();
      await qc.invalidateQueries({ queryKey: ["versions", projectId] });
    } catch (e) {
      setError(e);
    } finally {
      setBusy(false);
    }
  };

  const saveNamed = () =>
    run(async () => {
      await createVersion(projectId, label.trim());
      setLabel("");
    });

  const restore = (versionId: number) => {
    if (!window.confirm(t.versions.confirmRestore)) return;
    void run(async () => {
      const saved = await restoreVersion(projectId, versionId);
      usePipelineStore.getState().load(saved.pipeline);
      useUiStore.getState().setSaveStatus("saved");
      onClose();
    });
  };

  return (
    <Dialog
      open={open}
      onOpenChange={(o) => !o && onClose()}
      title={t.versions.title}
      description={t.versions.hint}
    >
      <div className="flex flex-col gap-3">
        <div className="flex gap-2">
          <Input
            value={label}
            placeholder={t.versions.namePlaceholder}
            onChange={(e) => setLabel(e.target.value)}
            aria-label={t.versions.namePlaceholder}
          />
          <Button disabled={!label.trim() || busy} onClick={() => void saveNamed()}>
            <Save /> {t.versions.saveNamed}
          </Button>
        </div>
        {error !== null && <IssueItem issue={errorIssue(error)} />}
        {isLoading && <Spinner />}
        {data?.length === 0 && <p className="text-xs text-muted-foreground">{t.versions.empty}</p>}
        <ul className="flex max-h-[50vh] flex-col divide-y overflow-auto rounded-md border">
          {data?.map((v) => (
            <li key={v.id} className="flex items-center gap-2 px-3 py-2">
              <div className="min-w-0 flex-1">
                <p className="truncate text-[13px] font-medium">
                  {v.label ?? <span className="text-muted-foreground">{t.versions.auto}</span>}
                </p>
                <p className="text-[11px] text-muted-foreground">
                  {fmtDateTime(v.created_at)} · {t.versions.nodes(v.node_count)}
                </p>
              </div>
              {v.label && <Badge tone="primary">v{v.version}</Badge>}
              <Button variant="outline" size="sm" disabled={busy} onClick={() => restore(v.id)}>
                <RotateCcw /> {t.versions.restore}
              </Button>
            </li>
          ))}
        </ul>
      </div>
    </Dialog>
  );
}
