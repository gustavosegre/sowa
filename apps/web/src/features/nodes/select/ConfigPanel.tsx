import { ArrowDown, ArrowUp } from "lucide-react";
import { useMemo, useState } from "react";

import type { Column, SelectConfig } from "@/api/types";
import { Button, Checkbox, Input } from "@/components/ui";
import { TypeIcon } from "@/components/TypeIcon";
import { t } from "@/i18n/pt-BR";
import { cn } from "@/lib/utils";

import type { ConfigPanelProps } from "../shared/panel";

/** Checkbox = column is kept. Reordering switches to "keep" mode with an explicit order. */
export function ConfigPanel({ config, update, columns }: ConfigPanelProps<SelectConfig>) {
  const [q, setQ] = useState("");
  const kept = useMemo(() => {
    if (config.mode === "keep") return config.columns;
    const dropped = new Set(config.columns);
    return columns.map((c) => c.name).filter((n) => !dropped.has(n));
  }, [config, columns]);
  const keptSet = new Set(kept);
  const byName = new Map(columns.map((c) => [c.name, c]));
  const ordered: Column[] = [
    ...kept.map((n) => byName.get(n) ?? { name: n, type: "other" as const }),
    ...columns.filter((c) => !keptSet.has(c.name)),
  ];
  const visible = q ? ordered.filter((c) => c.name.toLowerCase().includes(q.toLowerCase())) : ordered;

  const setKept = (names: string[], forceKeep = false) => {
    if (config.mode === "keep" || forceKeep) update({ ...config, mode: "keep", columns: names });
    else update({ ...config, columns: columns.map((c) => c.name).filter((n) => !names.includes(n)) });
  };
  const toggle = (name: string, on: boolean) =>
    setKept(on ? [...kept, name] : kept.filter((n) => n !== name));
  const move = (name: string, dir: -1 | 1) => {
    const i = kept.indexOf(name);
    const j = i + dir;
    if (i < 0 || j < 0 || j >= kept.length) return;
    const next = [...kept];
    [next[i], next[j]] = [next[j] ?? "", next[i] ?? ""];
    setKept(next, true);
  };
  const rename = (name: string, value: string) => {
    const renames = Object.fromEntries(Object.entries(config.renames).filter(([k]) => k !== name));
    if (value && value !== name) renames[name] = value;
    update({ ...config, renames });
  };

  return (
    <div className="flex flex-col gap-2">
      <div className="flex items-center gap-2">
        <Input placeholder={t.common.search} value={q} onChange={(e) => setQ(e.target.value)} />
        <Button variant="ghost" size="sm" onClick={() => setKept(columns.map((c) => c.name))}>
          {t.nodes.select.all}
        </Button>
        <Button variant="ghost" size="sm" onClick={() => setKept([])}>
          {t.nodes.select.noneSel}
        </Button>
      </div>
      <p className="text-[11px] text-muted-foreground">
        {kept.length} de {columns.length} colunas mantidas
        {config.mode === "keep"
          ? " · ordem personalizada"
          : " · novas colunas do arquivo entram automaticamente"}
      </p>
      <ul className="flex flex-col divide-y rounded-md border">
        {visible.map((c) => {
          const on = keptSet.has(c.name);
          const missing = !byName.has(c.name);
          return (
            <li key={c.name} className={cn("flex items-center gap-1.5 px-2 py-1", !on && "opacity-60")}>
              <Checkbox checked={on} onCheckedChange={(v) => toggle(c.name, v)} />
              <TypeIcon type={c.type} />
              <span
                className={cn("w-28 shrink-0 truncate text-[13px]", missing && "text-danger")}
                title={c.name}
              >
                {c.name}
              </span>
              <Input
                className="h-7 flex-1"
                placeholder={t.nodes.select.renameTo}
                defaultValue={config.renames[c.name] ?? ""}
                key={`${c.name}:${config.renames[c.name] ?? ""}`}
                onBlur={(e) => rename(c.name, e.target.value.trim())}
                onKeyDown={(e) => e.key === "Enter" && (e.target as HTMLInputElement).blur()}
                disabled={!on}
                aria-label={`${t.nodes.select.renameTo} ${c.name}`}
              />
              <Button
                variant="ghost"
                size="iconSm"
                disabled={!on}
                onClick={() => move(c.name, -1)}
                aria-label="Subir"
              >
                <ArrowUp />
              </Button>
              <Button
                variant="ghost"
                size="iconSm"
                disabled={!on}
                onClick={() => move(c.name, 1)}
                aria-label="Descer"
              >
                <ArrowDown />
              </Button>
            </li>
          );
        })}
      </ul>
    </div>
  );
}
