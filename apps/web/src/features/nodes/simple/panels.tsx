/** Config panels of the smaller Phase 2 nodes. */
import { Plus, Trash2 } from "lucide-react";

import type {
  BinConfig,
  DatePartsConfig,
  DistinctConfig,
  FillNullConfig,
  FillRule,
  ReplaceConfig,
  ReplaceRule,
  SampleNodeConfig,
  SplitConfig,
  TextCleanConfig,
  UnpivotConfig,
} from "@/api/types";
import { Button, Checkbox, Field, Input, Select, Switch } from "@/components/ui";
import { t } from "@/i18n/pt-BR";

import { ColumnMultiSelect, ColumnSelect } from "../shared/ColumnSelect";
import type { ConfigPanelProps } from "../shared/panel";
import { formatNumberList, parseNumberList, SortKeysEditor } from "../shared/SortKeysEditor";

const tt = t.nodes2;

/** Text input that commits on blur (lists typed as "a; b; c"). */
function ListInput({
  value,
  onCommit,
  placeholder,
}: {
  value: string;
  onCommit: (v: string) => void;
  placeholder?: string;
}) {
  return (
    <Input
      key={value}
      defaultValue={value}
      placeholder={placeholder}
      onBlur={(e) => e.target.value !== value && onCommit(e.target.value)}
      onKeyDown={(e) => e.key === "Enter" && (e.target as HTMLInputElement).blur()}
    />
  );
}

function splitList(text: string): string[] {
  return text
    .split(";")
    .map((x) => x.trim())
    .filter(Boolean);
}

export function DistinctPanel({ config, update, columns }: ConfigPanelProps<DistinctConfig>) {
  return (
    <div className="flex flex-col gap-3">
      <Field label={tt.keys}>
        <ColumnMultiSelect
          columns={columns}
          value={config.keys}
          onChange={(keys) => update({ ...config, keys })}
        />
      </Field>
      {config.keys.length > 0 && (
        <>
          <Field label={tt.keep}>
            <Select
              value={config.keep}
              options={[
                { value: "first", label: tt.keepFirst },
                { value: "last", label: tt.keepLast },
              ]}
              onChange={(keep) => update({ ...config, keep })}
            />
          </Field>
          <div className="flex flex-col gap-1">
            <span className="text-xs font-medium text-muted-foreground">{tt.orderBy}</span>
            <SortKeysEditor
              columns={columns}
              value={config.order_by}
              onChange={(order_by) => update({ ...config, order_by })}
            />
          </div>
        </>
      )}
    </div>
  );
}

export function SamplePanel({ config, update }: ConfigPanelProps<SampleNodeConfig>) {
  return (
    <div className="flex flex-col gap-3">
      <Field label={tt.mode}>
        <Select
          value={config.mode}
          options={[
            { value: "first", label: tt.sampleFirst },
            { value: "random", label: tt.sampleRandom },
            { value: "percent", label: tt.samplePercent },
          ]}
          onChange={(mode) => update({ ...config, mode })}
        />
      </Field>
      {config.mode === "percent" ? (
        <Field label={tt.percent}>
          <Input
            type="number"
            min={0.01}
            max={100}
            value={config.percent}
            onChange={(e) => update({ ...config, percent: Number(e.target.value) || 1 })}
          />
        </Field>
      ) : (
        <Field label={tt.rows}>
          <Input
            type="number"
            min={1}
            value={config.rows}
            onChange={(e) => update({ ...config, rows: Math.max(1, Number(e.target.value) || 1) })}
          />
        </Field>
      )}
      {config.mode !== "first" && (
        <Field label={tt.seed}>
          <Input
            type="number"
            value={config.seed}
            onChange={(e) => update({ ...config, seed: Number(e.target.value) || 0 })}
          />
        </Field>
      )}
    </div>
  );
}

export function TextCleanPanel({ config, update, columns }: ConfigPanelProps<TextCleanConfig>) {
  return (
    <div className="flex flex-col gap-3">
      <Field label={tt.columns}>
        <ColumnMultiSelect
          columns={columns.filter((c) => c.type === "text")}
          value={config.columns}
          onChange={(cols) => update({ ...config, columns: cols })}
        />
      </Field>
      <Switch checked={config.trim} onCheckedChange={(trim) => update({ ...config, trim })} label={tt.trim} />
      <Switch
        checked={config.collapse_spaces}
        onCheckedChange={(collapse_spaces) => update({ ...config, collapse_spaces })}
        label={tt.collapse}
      />
      <Switch
        checked={config.remove_accents}
        onCheckedChange={(remove_accents) => update({ ...config, remove_accents })}
        label={tt.accents}
      />
      <Switch
        checked={config.empty_as_null}
        onCheckedChange={(empty_as_null) => update({ ...config, empty_as_null })}
        label={tt.emptyNull}
      />
      <Field label={tt.case}>
        <Select
          value={config.case}
          options={[
            { value: "none", label: tt.caseNone },
            { value: "upper", label: tt.caseUpper },
            { value: "lower", label: tt.caseLower },
            { value: "title", label: tt.caseTitle },
          ]}
          onChange={(c) => update({ ...config, case: c })}
        />
      </Field>
    </div>
  );
}

export function ReplacePanel({ config, update, columns }: ConfigPanelProps<ReplaceConfig>) {
  const setRule = (i: number, patch: Partial<ReplaceRule>) =>
    update({ ...config, rules: config.rules.map((r, j) => (j === i ? { ...r, ...patch } : r)) });
  return (
    <div className="flex flex-col gap-3">
      <Field label={t.common.column}>
        <ColumnSelect
          columns={columns}
          value={config.column}
          onChange={(column) => update({ ...config, column })}
        />
      </Field>
      <Field label={tt.mode}>
        <Select
          value={config.mode}
          options={[
            { value: "exact", label: tt.replaceExact },
            { value: "contains", label: tt.replaceContains },
            { value: "regex", label: tt.replaceRegex },
          ]}
          onChange={(mode) => update({ ...config, mode })}
        />
      </Field>
      <div className="flex flex-col gap-1.5">
        <div className="grid grid-cols-[1fr_1fr_auto] gap-1.5 text-xs font-medium text-muted-foreground">
          <span>{tt.find}</span>
          <span>{tt.replaceWith}</span>
          <span className="w-6" />
        </div>
        {config.rules.map((r, i) => (
          <div key={i} className="grid grid-cols-[1fr_1fr_auto] gap-1.5">
            <Input
              className="h-7"
              value={r.find == null ? "" : String(r.find)}
              placeholder={config.mode === "exact" ? tt.emptyCell : ""}
              onChange={(e) => setRule(i, { find: e.target.value === "" ? null : e.target.value })}
              aria-label={tt.find}
            />
            <Input
              className="h-7"
              value={r.replace == null ? "" : String(r.replace)}
              onChange={(e) => setRule(i, { replace: e.target.value })}
              aria-label={tt.replaceWith}
            />
            <Button
              variant="ghost"
              size="iconSm"
              aria-label={t.common.remove}
              onClick={() => update({ ...config, rules: config.rules.filter((_, j) => j !== i) })}
            >
              <Trash2 />
            </Button>
          </div>
        ))}
        <Button
          variant="outline"
          size="sm"
          className="self-start"
          onClick={() => update({ ...config, rules: [...config.rules, { find: "", replace: "" }] })}
        >
          <Plus /> {tt.addRule}
        </Button>
      </div>
      <Checkbox
        checked={config.case_sensitive}
        onCheckedChange={(case_sensitive) => update({ ...config, case_sensitive })}
        label={tt.caseSensitive}
      />
    </div>
  );
}

export function FillNullPanel({ config, update, columns }: ConfigPanelProps<FillNullConfig>) {
  const setRule = (i: number, patch: Partial<FillRule>) =>
    update({ ...config, rules: config.rules.map((r, j) => (j === i ? { ...r, ...patch } : r)) });
  const directional = config.rules.some((r) => r.method === "previous" || r.method === "next");
  return (
    <div className="flex flex-col gap-3">
      {config.rules.map((r, i) => (
        <div key={i} className="flex flex-col gap-1.5 rounded-md border p-2">
          <div className="flex items-center gap-1.5">
            <ColumnSelect columns={columns} value={r.column} onChange={(column) => setRule(i, { column })} />
            <Button
              variant="ghost"
              size="iconSm"
              aria-label={t.common.remove}
              onClick={() => update({ ...config, rules: config.rules.filter((_, j) => j !== i) })}
            >
              <Trash2 />
            </Button>
          </div>
          <Select
            value={r.method}
            options={[
              { value: "value", label: tt.methodValue },
              { value: "previous", label: tt.methodPrevious },
              { value: "next", label: tt.methodNext },
              { value: "mean", label: tt.methodMean },
              { value: "median", label: tt.methodMedian },
            ]}
            onChange={(method) => setRule(i, { method })}
            aria-label={tt.method}
          />
          {r.method === "value" && (
            <Input
              className="h-7"
              value={r.value == null ? "" : String(r.value)}
              onChange={(e) => setRule(i, { value: e.target.value })}
              placeholder={t.common.value}
              aria-label={t.common.value}
            />
          )}
        </div>
      ))}
      <Button
        variant="outline"
        size="sm"
        className="self-start"
        onClick={() =>
          update({
            ...config,
            rules: [...config.rules, { column: columns[0]?.name ?? "", method: "value", value: null }],
          })
        }
      >
        <Plus /> {tt.addRule}
      </Button>
      {directional && (
        <div className="flex flex-col gap-1">
          <span className="text-xs font-medium text-muted-foreground">{tt.orderBy}</span>
          <SortKeysEditor
            columns={columns}
            value={config.order_by}
            onChange={(order_by) => update({ ...config, order_by })}
          />
        </div>
      )}
    </div>
  );
}

export function DatePartsPanel({ config, update, columns }: ConfigPanelProps<DatePartsConfig>) {
  const dates = columns.filter((c) => c.type === "date" || c.type === "datetime");
  const parts = Object.keys(tt.dateParts) as DatePartsConfig["parts"];
  return (
    <div className="flex flex-col gap-3">
      <Field label={t.common.column}>
        <ColumnSelect
          columns={dates}
          value={config.column}
          onChange={(column) => update({ ...config, column })}
        />
      </Field>
      <div className="grid grid-cols-1 gap-1.5">
        {parts.map((p) => (
          <Checkbox
            key={p}
            checked={config.parts.includes(p)}
            onCheckedChange={(on) =>
              update({ ...config, parts: on ? [...config.parts, p] : config.parts.filter((x) => x !== p) })
            }
            label={tt.dateParts[p]}
          />
        ))}
      </div>
      <Field label={tt.prefix}>
        <Input
          value={config.prefix ?? ""}
          placeholder={config.column ? `${config.column}_` : ""}
          onChange={(e) => update({ ...config, prefix: e.target.value === "" ? null : e.target.value })}
        />
      </Field>
    </div>
  );
}

export function BinPanel({ config, update, columns }: ConfigPanelProps<BinConfig>) {
  const numeric = columns.filter((c) => c.type === "integer" || c.type === "decimal");
  return (
    <div className="flex flex-col gap-3">
      <Field label={t.common.column}>
        <ColumnSelect
          columns={numeric}
          value={config.column}
          onChange={(column) => update({ ...config, column })}
        />
      </Field>
      <Field label={tt.mode}>
        <Select
          value={config.mode}
          options={[
            { value: "manual", label: tt.binManual },
            { value: "equal", label: tt.binEqual },
          ]}
          onChange={(mode) => update({ ...config, mode })}
        />
      </Field>
      {config.mode === "manual" ? (
        <Field label={tt.boundaries} hint="Ex.: 100; 500; 1.000 → < 100, 100 a 500, 500 a 1.000, ≥ 1.000">
          <ListInput
            value={formatNumberList(config.boundaries)}
            onCommit={(v) => update({ ...config, boundaries: parseNumberList(v) })}
          />
        </Field>
      ) : (
        <Field label={tt.count}>
          <Input
            type="number"
            min={2}
            max={100}
            value={config.count}
            onChange={(e) => update({ ...config, count: Math.max(2, Number(e.target.value) || 2) })}
          />
        </Field>
      )}
      <Field label={tt.newName}>
        <Input
          value={config.name}
          placeholder={config.column ? `${config.column}_faixa` : ""}
          onChange={(e) => update({ ...config, name: e.target.value })}
        />
      </Field>
    </div>
  );
}

export function SplitPanel({ config, update, columns }: ConfigPanelProps<SplitConfig>) {
  return (
    <div className="flex flex-col gap-3">
      <Field label={t.common.column}>
        <ColumnSelect
          columns={columns.filter((c) => c.type === "text")}
          value={config.column}
          onChange={(column) => update({ ...config, column })}
        />
      </Field>
      <Field label={tt.mode}>
        <Select
          value={config.mode}
          options={[
            { value: "delimiter", label: tt.splitDelimiter },
            { value: "position", label: tt.splitPosition },
            { value: "regex", label: tt.splitRegex },
          ]}
          onChange={(mode) => update({ ...config, mode })}
        />
      </Field>
      {config.mode === "delimiter" && (
        <Field label={tt.delimiter}>
          <Input
            value={config.delimiter}
            onChange={(e) => update({ ...config, delimiter: e.target.value })}
          />
        </Field>
      )}
      {config.mode === "position" && (
        <Field label={tt.positions} hint="Ex.: 3; 6 corta “ABCDEFGH” em “AB”, “CDE”, “FGH”.">
          <ListInput
            value={config.positions.join("; ")}
            onCommit={(v) => update({ ...config, positions: parseNumberList(v).map(Math.trunc) })}
          />
        </Field>
      )}
      {config.mode === "regex" && (
        <Field label={tt.pattern} hint="Ex.: (\d{5})-(\d{3}) separa um CEP em duas partes.">
          <Input
            value={config.pattern}
            onChange={(e) => update({ ...config, pattern: e.target.value })}
            className="font-mono"
          />
        </Field>
      )}
      {config.mode !== "position" && (
        <Field label={tt.parts}>
          <Input
            type="number"
            min={1}
            max={50}
            value={config.parts}
            onChange={(e) => update({ ...config, parts: Math.max(1, Number(e.target.value) || 1) })}
          />
        </Field>
      )}
      <Field label={tt.names}>
        <ListInput
          value={config.names.join("; ")}
          onCommit={(v) => update({ ...config, names: splitList(v) })}
        />
      </Field>
      <Switch
        checked={config.keep_original}
        onCheckedChange={(keep_original) => update({ ...config, keep_original })}
        label={tt.keepOriginal}
      />
      <Switch checked={config.trim} onCheckedChange={(trim) => update({ ...config, trim })} label={tt.trim} />
    </div>
  );
}

export function UnpivotPanel({ config, update, columns }: ConfigPanelProps<UnpivotConfig>) {
  return (
    <div className="flex flex-col gap-3">
      <Field label={tt.columns}>
        <ColumnMultiSelect
          columns={columns}
          value={config.columns}
          onChange={(cols) => update({ ...config, columns: cols })}
        />
      </Field>
      <div className="grid grid-cols-2 gap-2">
        <Field label={tt.nameColumn}>
          <Input
            value={config.name_column}
            onChange={(e) => update({ ...config, name_column: e.target.value })}
          />
        </Field>
        <Field label={tt.valueColumn}>
          <Input
            value={config.value_column}
            onChange={(e) => update({ ...config, value_column: e.target.value })}
          />
        </Field>
      </div>
      <Switch
        checked={config.drop_nulls}
        onCheckedChange={(drop_nulls) => update({ ...config, drop_nulls })}
        label={tt.dropNulls}
      />
    </div>
  );
}
