import { X } from "lucide-react";

import { useProfile } from "@/api/hooks";
import { Button, Spinner } from "@/components/ui";
import { TypeIcon } from "@/components/TypeIcon";
import { useServerPipeline } from "@/features/editor/analysis";
import { t } from "@/i18n/pt-BR";
import { fmtInt } from "@/lib/utils";

export function ProfilePanel({
  nodeId,
  hash,
  column,
  onClose,
}: {
  nodeId: string;
  hash: string | null | undefined;
  column: string;
  onClose: () => void;
}) {
  const pipeline = useServerPipeline((s) => s.pipeline);
  const { data, isLoading, error } = useProfile(pipeline, nodeId, hash, column);
  const maxTop = Math.max(1, ...(data?.top.map((x) => x.count) ?? [1]));
  const maxHist = Math.max(1, ...(data?.histogram.map((x) => x.count) ?? [1]));
  const tt = t.profile;

  return (
    <aside className="flex w-72 shrink-0 flex-col border-l bg-card" aria-label={t.preview.profile}>
      <div className="flex items-center gap-1.5 border-b px-3 py-2">
        {data && <TypeIcon type={data.type} />}
        <h3 className="min-w-0 flex-1 truncate text-[13px] font-semibold">{column}</h3>
        <Button variant="ghost" size="iconSm" onClick={onClose} aria-label={t.common.close}>
          <X />
        </Button>
      </div>
      <div className="flex min-h-0 flex-1 flex-col gap-3 overflow-auto p-3 text-[12px]">
        {isLoading && <Spinner />}
        {error && <p className="text-danger">{error.message}</p>}
        {data && (
          <>
            {data.sampled && (
              <p className="text-[11px] text-muted-foreground">
                {tt.sampled} ({fmtInt(data.rows)} linhas)
              </p>
            )}
            <dl className="grid grid-cols-2 gap-x-3 gap-y-1">
              <dt className="text-muted-foreground">{tt.nulls}</dt>
              <dd className="text-right font-mono">
                {fmtInt(data.nulls)} (
                {(data.null_pct * 100).toLocaleString("pt-BR", { maximumFractionDigits: 1 })}%)
              </dd>
              <dt className="text-muted-foreground">{tt.distinct}</dt>
              <dd className="text-right font-mono">{fmtInt(data.distinct)}</dd>
              {data.min !== null && (
                <>
                  <dt className="text-muted-foreground">{tt.min}</dt>
                  <dd className="truncate text-right font-mono" title={data.min}>
                    {data.min}
                  </dd>
                  <dt className="text-muted-foreground">{tt.max}</dt>
                  <dd className="truncate text-right font-mono" title={data.max ?? ""}>
                    {data.max}
                  </dd>
                </>
              )}
              {data.mean !== null && (
                <>
                  <dt className="text-muted-foreground">{tt.mean}</dt>
                  <dd className="text-right font-mono">
                    {data.mean.toLocaleString("pt-BR", { maximumFractionDigits: 4 })}
                  </dd>
                </>
              )}
            </dl>
            {data.histogram.length > 0 && (
              <div>
                <p className="mb-1 font-medium">{tt.histogram}</p>
                <div className="flex h-16 items-end gap-px" role="img" aria-label={tt.histogram}>
                  {data.histogram.map((b, i) => (
                    <div
                      key={i}
                      className="flex-1 rounded-t-sm bg-primary/70"
                      style={{ height: `${Math.max(2, (b.count / maxHist) * 100)}%` }}
                      title={`${String(b.from)} – ${String(b.to)}: ${fmtInt(b.count)}`}
                    />
                  ))}
                </div>
              </div>
            )}
            <div>
              <p className="mb-1 font-medium">{tt.top}</p>
              <ul className="flex flex-col gap-1">
                {data.top.map((x) => (
                  <li key={x.value ?? "∅"} className="relative overflow-hidden rounded px-1.5 py-0.5">
                    <div
                      className="absolute inset-y-0 left-0 bg-accent"
                      style={{ width: `${(x.count / maxTop) * 100}%` }}
                    />
                    <div className="relative flex justify-between gap-2">
                      <span className="truncate">{x.value}</span>
                      <span className="font-mono text-muted-foreground">{fmtInt(x.count)}</span>
                    </div>
                  </li>
                ))}
              </ul>
            </div>
          </>
        )}
      </div>
    </aside>
  );
}
