import { useMemo, useState } from "react";

import { allMetas, getMeta } from "@/features/nodes/registry";
import { CATEGORY_COLOR, CATEGORY_ORDER } from "@/features/nodes/types";
import { t } from "@/i18n/pt-BR";

function norm(s: string): string {
  return s.normalize("NFKD").replace(/[̀-ͯ]/g, "").toLowerCase();
}

/** Menu of node types: likely next steps first, then everything by category, with search. */
export function AddNodeMenu({ suggested, onPick }: { suggested: string[]; onPick: (type: string) => void }) {
  const [q, setQ] = useState("");
  const metas = useMemo(() => allMetas().filter((m) => m.type !== "source" && !m.annotation), []);
  const s = norm(q.trim());
  const filtered = s
    ? metas.filter((m) => norm(`${m.label} ${m.description} ${(m.keywords ?? []).join(" ")}`).includes(s))
    : null;
  const Item = ({ type }: { type: string }) => {
    const m = getMeta(type);
    if (!m) return null;
    const Icon = m.icon;
    return (
      <button
        type="button"
        className="flex w-full cursor-pointer items-center gap-2 rounded px-2 py-1.5 text-left text-[13px] hover:bg-muted"
        onClick={() => onPick(type)}
      >
        <Icon className="size-3.5 shrink-0" style={{ color: CATEGORY_COLOR[m.category] }} />
        <span className="truncate">{m.label}</span>
      </button>
    );
  };
  return (
    <div className="flex flex-col">
      <input
        autoFocus
        value={q}
        onChange={(e) => setQ(e.target.value)}
        placeholder={t.common.search}
        className="mb-1 h-7 rounded border-b bg-transparent px-2 text-[13px] outline-none"
        onKeyDown={(e) => {
          const first = filtered?.[0];
          if (e.key === "Enter" && first) onPick(first.type);
        }}
      />
      <div className="max-h-80 overflow-auto">
        {filtered ? (
          filtered.map((m) => <Item key={m.type} type={m.type} />)
        ) : (
          <>
            {suggested.length > 0 && (
              <>
                <p className="px-2 pt-1 text-[10px] font-semibold uppercase tracking-wide text-muted-foreground">
                  {t.editor.likelyNext}
                </p>
                {suggested.map((type) => (
                  <Item key={type} type={type} />
                ))}
                <div className="my-1 h-px bg-border" />
              </>
            )}
            {CATEGORY_ORDER.map((cat) => {
              const items = metas.filter((m) => m.category === cat);
              if (!items.length) return null;
              return (
                <div key={cat}>
                  <p className="px-2 pt-1 text-[10px] font-semibold uppercase tracking-wide text-muted-foreground">
                    {t.categories[cat]}
                  </p>
                  {items.map((m) => (
                    <Item key={m.type} type={m.type} />
                  ))}
                </div>
              );
            })}
          </>
        )}
      </div>
    </div>
  );
}
