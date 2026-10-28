import { Plus, Trash2 } from "lucide-react";

import type { CastConfig, CastRule, LogicalType } from "@/api/types";
import { Button, Checkbox, Field, Input, Select } from "@/components/ui";
import { TYPE_OPTIONS } from "@/components/TypeIcon";
import { t } from "@/i18n/pt-BR";

import { ColumnSelect } from "../shared/ColumnSelect";
import type { ConfigPanelProps } from "../shared/panel";

const DATE_FORMATS = [
  { value: "%d/%m/%Y", label: "dd/mm/aaaa" },
  { value: "%d/%m/%y", label: "dd/mm/aa" },
  { value: "%Y-%m-%d", label: "aaaa-mm-dd (ISO)" },
  { value: "%m/%d/%Y", label: "mm/dd/aaaa (EUA)" },
  { value: "%d-%m-%Y", label: "dd-mm-aaaa" },
  { value: "%d/%m/%Y %H:%M", label: "dd/mm/aaaa hh:mm" },
  { value: "%d/%m/%Y %H:%M:%S", label: "dd/mm/aaaa hh:mm:ss" },
  { value: "%Y-%m-%d %H:%M:%S", label: "aaaa-mm-dd hh:mm:ss" },
  { value: "%H:%M", label: "hh:mm" },
  { value: "%H:%M:%S", label: "hh:mm:ss" },
];

export function newRule(column: string, to: LogicalType, srcType?: LogicalType): CastRule {
  const rule: CastRule = {
    column,
    to,
    format: null,
    decimal_separator: null,
    precision: null,
    scale: null,
    on_error: "null",
  };
  if (srcType === "text" && (to === "date" || to === "datetime"))
    rule.format = to === "date" ? "%d/%m/%Y" : "%d/%m/%Y %H:%M:%S";
  if (srcType === "text" && (to === "decimal" || to === "integer")) rule.decimal_separator = ",";
  return rule;
}

export function ConfigPanel({ config, update, columns }: ConfigPanelProps<CastConfig>) {
  const tt = t.nodes.cast;
  const setRule = (i: number, patch: Partial<CastRule>) =>
    update({ ...config, casts: config.casts.map((r, j) => (j === i ? { ...r, ...patch } : r)) });
  const used = new Set(config.casts.map((r) => r.column));

  return (
    <div className="flex flex-col gap-3">
      {config.casts.map((r, i) => {
        const src = columns.find((c) => c.name === r.column)?.type;
        const fromText = src === "text";
        const temporal = r.to === "date" || r.to === "datetime" || r.to === "time";
        const numeric = r.to === "decimal" || r.to === "integer";
        return (
          <div key={i} className="flex flex-col gap-2 rounded-md border p-2.5">
            <div className="flex items-end gap-2">
              <Field label={t.common.column}>
                <ColumnSelect
                  columns={columns.filter((c) => c.name === r.column || !used.has(c.name))}
                  value={r.column}
                  onChange={(column) => setRule(i, { column })}
                />
              </Field>
              <Field label={tt.to}>
                <Select
                  value={r.to}
                  options={TYPE_OPTIONS}
                  onChange={(to) => setRule(i, { ...newRule(r.column, to, src), on_error: r.on_error })}
                />
              </Field>
              <Button
                variant="ghost"
                size="icon"
                aria-label={t.common.remove}
                onClick={() => update({ ...config, casts: config.casts.filter((_, j) => j !== i) })}
              >
                <Trash2 />
              </Button>
            </div>
            {temporal && (fromText || src === "date" || src === "datetime") && (
              <Field label={tt.format} hint={fromText ? "Como a data está escrita no texto." : undefined}>
                <Select
                  value={r.format ?? ""}
                  placeholder="Detectar (ISO)"
                  options={DATE_FORMATS}
                  onChange={(format) => setRule(i, { format })}
                />
              </Field>
            )}
            {r.to === "text" && (src === "date" || src === "datetime") && (
              <Field label={tt.format}>
                <Select
                  value={r.format ?? ""}
                  placeholder="Padrão (dd/mm/aaaa)"
                  options={DATE_FORMATS}
                  onChange={(format) => setRule(i, { format })}
                />
              </Field>
            )}
            {numeric && fromText && (
              <Field label={tt.decimal}>
                <Select
                  value={r.decimal_separator ?? ""}
                  placeholder="Ponto (padrão SQL)"
                  options={[
                    { value: ",", label: "Vírgula — 1.234,56" },
                    { value: ".", label: "Ponto — 1,234.56" },
                  ]}
                  onChange={(d) => setRule(i, { decimal_separator: d })}
                />
              </Field>
            )}
            {r.to === "decimal" && (
              <div className="flex items-center gap-2">
                <Checkbox
                  checked={r.precision != null}
                  onCheckedChange={(on) =>
                    setRule(i, on ? { precision: 18, scale: 2 } : { precision: null, scale: null })
                  }
                  label={tt.precision}
                />
                {r.precision != null && (
                  <>
                    <Input
                      className="h-7 w-14"
                      type="number"
                      value={r.precision}
                      aria-label="Precisão"
                      onChange={(e) => setRule(i, { precision: Number(e.target.value) || 18 })}
                    />
                    <Input
                      className="h-7 w-14"
                      type="number"
                      value={r.scale ?? 2}
                      aria-label="Casas decimais"
                      onChange={(e) => setRule(i, { scale: Number(e.target.value) })}
                    />
                  </>
                )}
              </div>
            )}
            <Field label={tt.onError}>
              <Select
                value={r.on_error}
                options={[
                  { value: "null", label: tt.onErrorNull },
                  { value: "error", label: tt.onErrorError },
                ]}
                onChange={(on_error) => setRule(i, { on_error })}
              />
            </Field>
          </div>
        );
      })}
      <Button
        variant="outline"
        size="sm"
        className="self-start"
        onClick={() => {
          const first = columns.find((c) => !used.has(c.name));
          update({ ...config, casts: [...config.casts, newRule(first?.name ?? "", "text", first?.type)] });
        }}
      >
        <Plus /> {tt.addRule}
      </Button>
    </div>
  );
}
