import { BookOpen, ChevronRight } from "lucide-react";
import { useMemo, useState } from "react";

import { useFunctions } from "@/api/hooks";
import { Input } from "@/components/ui";
import { t } from "@/i18n/pt-BR";
import { cn } from "@/lib/utils";

function norm(s: string): string {
  return s.normalize("NFKD").replace(/[̀-ͯ]/g, "").toLowerCase();
}

/** Searchable function reference, generated from the backend catalog. */
export function FunctionHelp({ context }: { context: "row" | "aggregate" }) {
  const [open, setOpen] = useState(false);
  const [q, setQ] = useState("");
  const { data = [] } = useFunctions();
  const groups = useMemo(() => {
    const s = norm(q.trim());
    const list = data.filter(
      (f) =>
        (context === "aggregate" || f.context === "row") &&
        (!s ||
          norm(f.name).includes(s) ||
          f.aliases.some((a) => norm(a).includes(s)) ||
          norm(f.description).includes(s)),
    );
    const out = new Map<string, typeof list>();
    for (const f of list) out.set(f.category, [...(out.get(f.category) ?? []), f]);
    return [...out.entries()];
  }, [data, q, context]);

  return (
    <div className="rounded-md border">
      <button
        type="button"
        className="flex w-full cursor-pointer items-center gap-1.5 px-2.5 py-1.5 text-xs font-medium text-muted-foreground hover:text-foreground"
        onClick={() => setOpen((o) => !o)}
        aria-expanded={open}
      >
        <ChevronRight className={cn("size-3.5 transition-transform", open && "rotate-90")} />
        <BookOpen className="size-3.5" />
        {t.formula.help}
      </button>
      {open && (
        <div className="flex max-h-72 flex-col gap-2 overflow-auto border-t p-2">
          <Input
            placeholder={t.common.search}
            value={q}
            onChange={(e) => setQ(e.target.value)}
            className="h-7"
          />
          {groups.map(([cat, fns]) => (
            <div key={cat}>
              <p className="mb-1 text-[10px] font-semibold uppercase tracking-wide text-muted-foreground">
                {cat}
              </p>
              <ul className="flex flex-col gap-1.5">
                {fns.map((f) => (
                  <li key={f.name} className="text-[12px]">
                    <code className="font-mono font-semibold text-cat-columns">{f.signature}</code>
                    <p className="text-muted-foreground">{f.description}</p>
                    <code className="font-mono text-[11px] text-muted-foreground">{f.example}</code>
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
