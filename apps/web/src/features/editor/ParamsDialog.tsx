import { Plus, Trash2 } from "lucide-react";
import { useState } from "react";

import type { Parameter } from "@/api/types";
import { Button, Dialog, Input, Select } from "@/components/ui";
import { TYPE_OPTIONS } from "@/components/TypeIcon";
import { t } from "@/i18n/pt-BR";
import { usePipelineStore } from "@/stores/pipelineStore";

/** Global parameters ({data_corte}): edited as a draft, applied in one undoable step. */
export function ParamsDialog({ open, onClose }: { open: boolean; onClose: () => void }) {
  const current = usePipelineStore((s) => s.pipeline.settings.params);
  const [draft, setDraft] = useState<Parameter[]>(current);
  const set = (i: number, patch: Partial<Parameter>) =>
    setDraft(draft.map((p, j) => (j === i ? { ...p, ...patch } : p)));
  const names = draft.map((p) => p.name.trim());
  const invalid = names.some((n, i) => !n || /[{}[\]]/.test(n) || names.indexOf(n) !== i);
  return (
    <Dialog
      open={open}
      onOpenChange={(o) => {
        if (o) setDraft(current);
        else onClose();
      }}
      title={t.params.title}
      description={t.params.hint}
      footer={
        <>
          <Button variant="outline" onClick={onClose}>
            {t.common.cancel}
          </Button>
          <Button
            disabled={invalid}
            onClick={() => {
              usePipelineStore.getState().setParams(draft.map((p) => ({ ...p, name: p.name.trim() })));
              onClose();
            }}
          >
            {t.common.save}
          </Button>
        </>
      }
    >
      <div className="flex flex-col gap-2">
        {!draft.length && <p className="text-xs text-muted-foreground">{t.params.empty}</p>}
        {draft.map((p, i) => (
          <div key={i} className="grid grid-cols-[1fr_8rem_1fr_auto] items-center gap-2">
            <div className="flex items-center gap-0.5 font-mono text-xs text-muted-foreground">
              {"{"}
              <Input
                value={p.name}
                onChange={(e) => set(i, { name: e.target.value })}
                aria-label={t.params.name}
              />
              {"}"}
            </div>
            <Select
              value={p.type}
              options={TYPE_OPTIONS}
              onChange={(type) => set(i, { type })}
              aria-label={t.params.type}
            />
            <Input
              value={p.value == null ? "" : String(p.value)}
              placeholder={p.type === "date" ? "dd/mm/aaaa" : ""}
              onChange={(e) => set(i, { value: e.target.value })}
              aria-label={t.params.value}
            />
            <Button
              variant="ghost"
              size="iconSm"
              onClick={() => setDraft(draft.filter((_, j) => j !== i))}
              aria-label={t.common.remove}
            >
              <Trash2 />
            </Button>
          </div>
        ))}
        <Button
          variant="outline"
          size="sm"
          className="self-start"
          onClick={() => setDraft([...draft, { name: `param_${draft.length + 1}`, type: "text", value: "" }])}
        >
          <Plus /> {t.params.add}
        </Button>
      </div>
    </Dialog>
  );
}
