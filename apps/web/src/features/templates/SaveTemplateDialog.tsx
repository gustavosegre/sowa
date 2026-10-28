import { useQueryClient } from "@tanstack/react-query";
import { BookmarkPlus } from "lucide-react";
import { useMemo, useState } from "react";

import { errorIssue } from "@/api/client";
import { createTemplate, updateTemplate, useSources, useTemplates } from "@/api/hooks";
import { IssueItem } from "@/components/IssueList";
import { Button, Dialog, Field, Input, Select, Textarea } from "@/components/ui";
import { useProjectId } from "@/features/editor/project";
import { getMeta } from "@/features/nodes/registry";
import { t } from "@/i18n/pt-BR";
import { usePipelineStore } from "@/stores/pipelineStore";

import { flowFromSelection } from "./flow";

const NEW = "__new__";

/** Saves the selected nodes (or just `nodeIds`) as a template, new or replacing one. */
export function SaveTemplateDialog({
  nodeIds,
  open,
  onClose,
}: {
  nodeIds: string[];
  open: boolean;
  onClose: () => void;
}) {
  const qc = useQueryClient();
  const pipeline = usePipelineStore((s) => s.pipeline);
  const { data: templates } = useTemplates();
  const { data: sources } = useSources(useProjectId());
  const first = pipeline.nodes.find((n) => n.id === nodeIds[0]);
  const [name, setName] = useState(first?.ui.label ?? "");
  const [description, setDescription] = useState("");
  const [replace, setReplace] = useState<string>(NEW);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>(null);

  const flow = useMemo(() => {
    const labelOf = (id: string) => {
      const n = pipeline.nodes.find((x) => x.id === id);
      if (!n) return id;
      const file =
        n.type === "source"
          ? sources?.find((s) => s.id === (typeof n.config.source_id === "string" ? n.config.source_id : ""))
              ?.name
          : undefined;
      return n.ui.label || file || getMeta(n.type)?.label || n.type;
    };
    return flowFromSelection(pipeline, nodeIds, labelOf);
  }, [pipeline, nodeIds, sources]);

  const outputNode = flow.nodes.find((n) => n.id === flow.output);

  const save = async () => {
    setBusy(true);
    setError(null);
    try {
      const body = { name: name.trim(), description: description.trim(), flow };
      if (replace === NEW) await createTemplate(body);
      else await updateTemplate(replace, body);
      await qc.invalidateQueries({ queryKey: ["templates"] });
      onClose();
    } catch (e) {
      setError(e);
    } finally {
      setBusy(false);
    }
  };

  return (
    <Dialog
      open={open}
      onOpenChange={(o) => !o && onClose()}
      title={t.templates.saveTitle}
      description={t.templates.selection(nodeIds.length)}
      footer={
        <Button onClick={() => void save()} disabled={busy || !name.trim()}>
          <BookmarkPlus /> {t.common.save}
        </Button>
      }
    >
      <div className="flex flex-col gap-3">
        {nodeIds.length === 1 && (
          <p className="text-[12px] text-muted-foreground">{t.templates.selectionHint}</p>
        )}
        <Field label={t.templates.name}>
          <Input value={name} onChange={(e) => setName(e.target.value)} autoFocus />
        </Field>
        <Field label={t.templates.description}>
          <Textarea rows={2} value={description} onChange={(e) => setDescription(e.target.value)} />
        </Field>
        {Boolean(templates?.length) && (
          <Field label={t.templates.replace}>
            <Select
              value={replace}
              onChange={setReplace}
              options={[
                { value: NEW, label: t.templates.replaceNone },
                ...(templates ?? []).map((x) => ({ value: x.id, label: x.name })),
              ]}
            />
          </Field>
        )}
        <div className="rounded-md border bg-muted/40 p-2 text-[12px]">
          <p>{t.templates.inputsOf(flow.inputs.map((i) => i.name))}</p>
          <p className={outputNode ? undefined : "text-warning"}>
            {outputNode
              ? t.templates.outputIs(
                  outputNode.ui.label || getMeta(outputNode.type)?.label || outputNode.type,
                )
              : t.templates.noOutput}
          </p>
        </div>
        {error !== null && <IssueItem issue={errorIssue(error)} />}
      </div>
    </Dialog>
  );
}
