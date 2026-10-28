import { AlertTriangle, ChevronRight, CircleX, Info } from "lucide-react";
import { useState } from "react";

import type { Issue } from "@/api/types";
import { t } from "@/i18n/pt-BR";
import { cn } from "@/lib/utils";

export function IssueItem({ issue, compact = false }: { issue: Issue; compact?: boolean }) {
  const [open, setOpen] = useState(false);
  const severity = issue.severity ?? "error";
  const Icon = severity === "error" ? CircleX : severity === "warning" ? AlertTriangle : Info;
  return (
    <div
      role={severity === "error" ? "alert" : "status"}
      className={cn(
        "rounded-md border px-2.5 py-2 text-[12px]",
        severity === "error" && "border-danger/30 bg-danger-soft",
        severity === "warning" && "border-warning/40 bg-warning-soft",
        severity === "info" && "bg-muted",
      )}
    >
      <div className="flex gap-2">
        <Icon
          className={cn(
            "mt-px size-3.5 shrink-0",
            severity === "error"
              ? "text-danger"
              : severity === "warning"
                ? "text-warning"
                : "text-muted-foreground",
          )}
        />
        <div className="min-w-0 flex-1">
          <p className="leading-snug">{issue.message}</p>
          {!compact && issue.hint && <p className="mt-0.5 text-muted-foreground">{issue.hint}</p>}
          {!compact && issue.examples && issue.examples.length > 0 && (
            <p className="mt-1 text-muted-foreground">
              {t.issues.examples}:{" "}
              {issue.examples.map((e, i) => (
                <code key={i} className="mr-1 rounded bg-card px-1 font-mono text-[11px]">
                  {e}
                </code>
              ))}
            </p>
          )}
          {!compact && issue.detail && (
            <button
              type="button"
              className="mt-1 flex cursor-pointer items-center gap-0.5 text-[11px] text-muted-foreground hover:text-foreground"
              onClick={() => setOpen((o) => !o)}
            >
              <ChevronRight className={cn("size-3 transition-transform", open && "rotate-90")} />
              {t.common.technicalDetail}
            </button>
          )}
          {open && issue.detail && (
            <pre className="mt-1 max-h-40 overflow-auto whitespace-pre-wrap rounded bg-card p-1.5 font-mono text-[10px] text-muted-foreground">
              {issue.detail}
            </pre>
          )}
        </div>
      </div>
    </div>
  );
}

export function IssueList({ issues, compact }: { issues: Issue[]; compact?: boolean }) {
  if (!issues.length) return null;
  return (
    <div className="flex flex-col gap-1.5">
      {issues.map((i, idx) => (
        <IssueItem key={`${i.code}-${i.column ?? ""}-${idx}`} issue={i} compact={compact} />
      ))}
    </div>
  );
}
