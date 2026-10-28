import { RefreshCw, Ungroup } from "lucide-react";
import { useState } from "react";

import { fetchTemplate, useTemplates } from "@/api/hooks";
import type { SubflowConfig } from "@/api/types";
import { Button } from "@/components/ui";
import { localizeFlow } from "@/features/editor/locale";
import { t } from "@/i18n/pt-BR";
import { usePipelineStore } from "@/stores/pipelineStore";

import { getMeta } from "../registry";
import type { ConfigPanelProps } from "../shared/panel";

export function ConfigPanel({ node, config, update }: ConfigPanelProps<SubflowConfig>) {
  const { data: templates } = useTemplates();
  const [busy, setBusy] = useState(false);
  const template = templates?.find((x) => x.id === config.template_id);
  const outdated = template !== undefined && template.version > config.template_version;
  const flow = config.flow;

  const refresh = async () => {
    if (!config.template_id) return;
    setBusy(true);
    try {
      const fresh = await fetchTemplate(config.template_id);
      update({ ...config, template_name: fresh.name, template_version: fresh.version, flow: fresh.flow });
    } finally {
      setBusy(false);
    }
  };

  const expand = async () => {
    setBusy(true);
    try {
      const locale = usePipelineStore.getState().pipeline.settings.locale;
      usePipelineStore.getState().expandSubflow(node.id, await localizeFlow(flow, locale));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="flex flex-col gap-3">
      <div className="rounded-md border bg-muted/40 p-2 text-[12px]">
        <p className="font-medium">{config.template_name || t.templates.untitled}</p>
        <p className="text-muted-foreground">
          {config.template_id && templates && !template
            ? t.templates.deleted
            : t.templates.version(config.template_version)}
        </p>
      </div>
      {outdated && (
        <Button size="sm" onClick={() => void refresh()} disabled={busy}>
          <RefreshCw /> {t.templates.update(template.version)}
        </Button>
      )}
      <div className="flex flex-col gap-1">
        <span className="text-xs font-medium text-muted-foreground">{t.templates.steps}</span>
        <ol className="flex flex-col gap-0.5">
          {flow.nodes
            .filter((n) => !getMeta(n.type)?.annotation)
            .map((n) => {
              const m = getMeta(n.type);
              const Icon = m?.icon;
              return (
                <li key={n.id} className="flex items-center gap-1.5 text-[12px]">
                  {Icon && <Icon className="size-3.5 shrink-0 text-muted-foreground" aria-hidden />}
                  <span className="truncate">{n.ui.label || m?.label || n.type}</span>
                  {n.id === flow.output && (
                    <span className="text-[10px] uppercase text-muted-foreground">{t.templates.output}</span>
                  )}
                </li>
              );
            })}
        </ol>
      </div>
      <Button size="sm" variant="outline" onClick={() => void expand()} disabled={busy}>
        <Ungroup /> {t.templates.expand}
      </Button>
      <p className="text-[11px] text-muted-foreground">{t.templates.expandHint}</p>
    </div>
  );
}
