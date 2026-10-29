import { useQueryClient } from "@tanstack/react-query";
import { CheckCircle2, FileUp, RotateCw } from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";

import { ApiError, errorIssue } from "@/api/client";
import { confirmImport, redetect, replaceSourceFile, uploadSource } from "@/api/hooks";
import type { ColumnPlan, Detection, ImportOptions, ImportReport, Source } from "@/api/types";
import { IssueItem } from "@/components/IssueList";
import { Button, Checkbox, Dialog, Field, Input, Select, Spinner, Switch } from "@/components/ui";
import { TYPE_OPTIONS, TypeIcon } from "@/components/TypeIcon";
import { useProjectId } from "@/features/editor/project";
import { t } from "@/i18n/pt-BR";
import { cn, fmtInt } from "@/lib/utils";
import { usePipelineStore } from "@/stores/pipelineStore";
import { useUiStore } from "@/stores/uiStore";

type Step = "file" | "settings" | "types" | "done";

const DATE_FORMATS = [
  { value: "%d/%m/%Y", label: "dd/mm/aaaa" },
  { value: "%Y-%m-%d", label: "aaaa-mm-dd" },
  { value: "%m/%d/%Y", label: "mm/dd/aaaa" },
  { value: "%d/%m/%y", label: "dd/mm/aa" },
  { value: "%d/%m/%Y %H:%M", label: "dd/mm/aaaa hh:mm" },
  { value: "%d/%m/%Y %H:%M:%S", label: "dd/mm/aaaa hh:mm:ss" },
  { value: "%H:%M", label: "hh:mm" },
  { value: "%H:%M:%S", label: "hh:mm:ss" },
];

function errorOf(e: unknown): ApiError {
  return e instanceof ApiError ? e : new ApiError(undefined, 0);
}

function Steps({ step }: { step: Step }) {
  const steps: [Step, string][] = [
    ["file", t.wizard.stepFile],
    ["settings", t.wizard.stepSettings],
    ["types", t.wizard.stepTypes],
  ];
  const idx = step === "done" ? 3 : steps.findIndex(([s]) => s === step);
  return (
    <ol className="mb-4 flex items-center gap-2 text-xs">
      {steps.map(([s, label], i) => (
        <li
          key={s}
          className={cn("flex items-center gap-1.5", i <= idx ? "text-foreground" : "text-muted-foreground")}
        >
          <span
            className={cn(
              "flex size-5 items-center justify-center rounded-full border text-[11px] font-semibold",
              i < idx && "border-primary bg-primary text-primary-foreground",
              i === idx && "border-primary text-primary",
            )}
          >
            {i + 1}
          </span>
          {label}
          {i < steps.length - 1 && <span className="mx-1 h-px w-6 bg-border" />}
        </li>
      ))}
    </ol>
  );
}

function SampleTable({ detection }: { detection: Detection }) {
  return (
    <div className="max-h-56 overflow-auto rounded-md border">
      <table className="w-full border-collapse text-[11px]">
        <thead className="sticky top-0 bg-muted">
          <tr>
            {detection.columns.map((c) => (
              <th key={c.name} className="whitespace-nowrap border-b px-2 py-1 text-left font-semibold">
                {c.name}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {detection.sample_rows.map((r, i) => (
            <tr key={i} className="odd:bg-card even:bg-muted/40">
              {detection.columns.map((_, j) => (
                <td key={j} className="max-w-48 truncate whitespace-nowrap px-2 py-0.5 font-mono">
                  {r[j] ?? <span className="text-muted-foreground">∅</span>}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export function ImportWizard() {
  const wizard = useUiStore((s) => s.wizard);
  const close = useUiStore((s) => s.closeWizard);
  const projectId = useProjectId();
  const qc = useQueryClient();
  const [step, setStep] = useState<Step>("file");
  const [progress, setProgress] = useState<number | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<ApiError | null>(null);
  const [source, setSource] = useState<Source | null>(null);
  const [detection, setDetection] = useState<Detection | null>(null);
  const [options, setOptions] = useState<ImportOptions | null>(null);
  const [report, setReport] = useState<ImportReport | null>(null);
  const [over, setOver] = useState(false);
  const input = useRef<HTMLInputElement>(null);

  const reset = useCallback(() => {
    setStep("file");
    setProgress(null);
    setBusy(false);
    setError(null);
    setSource(null);
    setDetection(null);
    setOptions(null);
    setReport(null);
  }, []);

  const upload = useCallback(
    async (file: File) => {
      setError(null);
      setBusy(true);
      setProgress(0);
      try {
        const res = wizard.replaceSourceId
          ? await replaceSourceFile(wizard.replaceSourceId, file, setProgress)
          : await uploadSource(file, projectId, setProgress);
        setSource(res.source);
        void qc.invalidateQueries({ queryKey: ["sources"] });
        if (res.error || !res.detection) {
          setError(new ApiError(res.error ?? undefined, 422));
          return;
        }
        setDetection(res.detection);
        setOptions(res.detection.options);
        setStep("settings");
      } catch (e) {
        setError(errorOf(e));
      } finally {
        setBusy(false);
        setProgress(null);
      }
    },
    [projectId, qc, wizard.replaceSourceId],
  );

  // Opened with a file dropped on the canvas.
  useEffect(() => {
    if (wizard.open) {
      reset();
      if (wizard.file) void upload(wizard.file);
    }
  }, [wizard.open, wizard.file, reset, upload]);

  const reread = async () => {
    if (!source || !options) return;
    setBusy(true);
    setError(null);
    try {
      const d = await redetect(source.id, options);
      setDetection(d);
      setOptions(d.options);
    } catch (e) {
      setError(errorOf(e));
    } finally {
      setBusy(false);
    }
  };

  const doImport = async () => {
    if (!source || !options) return;
    setBusy(true);
    setError(null);
    try {
      const out = await confirmImport(source.id, options);
      setReport(out.report);
      setSource(out.source);
      setStep("done");
      await qc.invalidateQueries({ queryKey: ["sources"] });
      await qc.invalidateQueries({ queryKey: ["schema"] });
      if (!wizard.replaceSourceId) {
        const store = usePipelineStore.getState();
        const sources = store.pipeline.nodes.filter((n) => n.type === "source").length;
        store.addNode("source", {
          config: { source_id: out.source.id },
          position: { x: 60, y: 60 + sources * 140 },
        });
      }
    } catch (e) {
      setError(errorOf(e));
    } finally {
      setBusy(false);
    }
  };

  const setCsv = (patch: Partial<NonNullable<ImportOptions["csv"]>>) =>
    options?.csv && setOptions({ ...options, csv: { ...options.csv, ...patch } });
  const setXlsx = (patch: Partial<NonNullable<ImportOptions["xlsx"]>>) =>
    options?.xlsx && setOptions({ ...options, xlsx: { ...options.xlsx, ...patch } });
  const setCol = (i: number, patch: Partial<ColumnPlan>) =>
    options &&
    setOptions({ ...options, columns: options.columns.map((c, j) => (j === i ? { ...c, ...patch } : c)) });

  const footer =
    step === "settings" ? (
      <>
        <Button variant="outline" onClick={() => void reread()} disabled={busy}>
          <RotateCw /> {t.wizard.reread}
        </Button>
        <Button onClick={() => setStep("types")} disabled={busy}>
          {t.common.next}
        </Button>
      </>
    ) : step === "types" ? (
      <>
        <Button variant="outline" onClick={() => setStep("settings")} disabled={busy}>
          {t.common.back}
        </Button>
        <Button onClick={() => void doImport()} disabled={busy}>
          {busy ? <Spinner /> : null}
          {busy ? t.wizard.importing : t.wizard.import}
        </Button>
      </>
    ) : step === "done" ? (
      <Button onClick={close}>{t.common.close}</Button>
    ) : undefined;

  return (
    <Dialog
      open={wizard.open}
      onOpenChange={(o) => !o && close()}
      title={wizard.replaceSourceId ? t.nodes.source.replace : t.wizard.title}
      description={source ? source.filename : t.wizard.formats}
      className="w-[min(860px,calc(100vw-32px))]"
      footer={footer}
    >
      <Steps step={step} />
      {error && (
        <div className="mb-3">
          <IssueItem issue={errorIssue(error)} />
        </div>
      )}

      {step === "file" && (
        <div
          className={cn(
            "flex cursor-pointer flex-col items-center justify-center gap-2 rounded-lg border-2 border-dashed p-10 text-center transition-colors",
            over ? "border-primary bg-primary/5" : "hover:bg-muted/50",
          )}
          onClick={() => input.current?.click()}
          onDragOver={(e) => (e.preventDefault(), setOver(true))}
          onDragLeave={() => setOver(false)}
          onDrop={(e) => {
            e.preventDefault();
            setOver(false);
            const f = e.dataTransfer.files[0];
            if (f) void upload(f);
          }}
          role="button"
          tabIndex={0}
          onKeyDown={(e) => e.key === "Enter" && input.current?.click()}
        >
          {busy ? <Spinner className="size-6 text-primary" /> : <FileUp className="size-8 text-primary" />}
          <p className="text-[13px] font-medium">
            {busy
              ? progress !== null && progress < 1
                ? `${t.wizard.uploading} ${Math.round(progress * 100)}%`
                : t.wizard.detecting
              : t.wizard.dropOrChoose}
          </p>
          <p className="text-xs text-muted-foreground">{t.wizard.formats}</p>
          <input
            ref={input}
            type="file"
            className="hidden"
            accept=".csv,.tsv,.txt,.parquet,.xlsx,.xlsm,.json,.ndjson,.jsonl"
            onChange={(e) => {
              const f = e.target.files?.[0];
              if (f) void upload(f);
              e.target.value = "";
            }}
            data-testid="file-input"
          />
        </div>
      )}

      {step === "settings" && detection && options && (
        <div className="flex flex-col gap-3">
          {detection.notes.map((n) => (
            <p key={n} className="rounded-md bg-accent px-2.5 py-1.5 text-xs">
              {n}
            </p>
          ))}
          {options.csv && (
            <div className="grid grid-cols-3 gap-3">
              <Field label={t.wizard.encoding}>
                <Select
                  value={options.csv.encoding}
                  options={Object.entries(t.wizard.encodings).map(([value, label]) => ({ value, label }))}
                  onChange={(encoding) => setCsv({ encoding })}
                />
              </Field>
              <Field label={t.wizard.delimiter}>
                <Select
                  value={options.csv.delimiter}
                  options={Object.entries(t.wizard.delimiters).map(([value, label]) => ({ value, label }))}
                  onChange={(delimiter) => setCsv({ delimiter })}
                />
              </Field>
              <Field label={t.wizard.decimalSeparator}>
                <Select
                  value={options.csv.decimal_separator}
                  options={[
                    { value: ",", label: "Vírgula — 1.234,56" },
                    { value: ".", label: "Ponto — 1,234.56" },
                  ]}
                  onChange={(decimal_separator) => setCsv({ decimal_separator })}
                />
              </Field>
              <Field label={t.wizard.skipRows}>
                <Input
                  type="number"
                  min={0}
                  value={options.csv.skip_rows}
                  onChange={(e) => setCsv({ skip_rows: Math.max(0, Number(e.target.value) || 0) })}
                />
              </Field>
              <Field label={t.wizard.quote}>
                <Input
                  value={options.csv.quote}
                  maxLength={1}
                  onChange={(e) => setCsv({ quote: e.target.value })}
                />
              </Field>
              <div className="flex items-end pb-1.5">
                <Switch
                  checked={options.csv.header}
                  onCheckedChange={(header) => setCsv({ header })}
                  label={t.wizard.header}
                />
              </div>
            </div>
          )}
          {options.xlsx && (
            <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
              <Field label={t.wizard.sheet}>
                <Select
                  value={options.xlsx.sheet ?? ""}
                  options={detection.sheets.map((s) => ({ value: s, label: s }))}
                  onChange={(sheet) => setXlsx({ sheet })}
                />
              </Field>
              <Field label={t.wizard.cellRange} hint={t.wizard.cellRangeHint}>
                <Input
                  value={options.xlsx.cell_range ?? ""}
                  placeholder="B3:F200"
                  maxLength={20}
                  onChange={(e) => setXlsx({ cell_range: e.target.value.trim() || null })}
                  onKeyDown={(e) => e.key === "Enter" && void reread()}
                />
              </Field>
              <Field label={t.wizard.skipRows}>
                <Input
                  type="number"
                  min={0}
                  value={options.xlsx.skip_rows}
                  onChange={(e) => setXlsx({ skip_rows: Math.max(0, Number(e.target.value) || 0) })}
                />
              </Field>
              <div className="flex items-end pb-1.5">
                <Switch
                  checked={options.xlsx.header}
                  onCheckedChange={(header) => setXlsx({ header })}
                  label={t.wizard.header}
                />
              </div>
            </div>
          )}
          <p className="text-xs font-medium text-muted-foreground">{t.wizard.sample}</p>
          <SampleTable detection={detection} />
        </div>
      )}

      {step === "types" && detection && options && (
        <div className="max-h-[52vh] overflow-auto rounded-md border">
          <table className="w-full border-collapse text-[12px]">
            <thead className="sticky top-0 z-10 bg-muted text-left text-[11px] text-muted-foreground">
              <tr>
                <th className="w-8 px-2 py-1.5">{t.wizard.include}</th>
                <th className="px-2 py-1.5">{t.wizard.originalName}</th>
                <th className="px-2 py-1.5">{t.wizard.finalName}</th>
                <th className="w-32 px-2 py-1.5">{t.common.type}</th>
                <th className="w-40 px-2 py-1.5">{t.wizard.format}</th>
                <th className="px-2 py-1.5">{t.issues.examples}</th>
              </tr>
            </thead>
            <tbody className="divide-y">
              {options.columns.map((c, i) => {
                const guess = detection.columns.find((g) => g.name === c.source);
                const temporal = c.type === "date" || c.type === "datetime" || c.type === "time";
                const numeric = c.type === "decimal" || c.type === "integer";
                const fromText = guess?.original_type === "text";
                return (
                  <tr key={c.source} className={cn(!c.include && "opacity-50")}>
                    <td className="px-2 py-1">
                      <Checkbox checked={c.include} onCheckedChange={(include) => setCol(i, { include })} />
                    </td>
                    <td className="max-w-40 truncate px-2 py-1 font-mono text-[11px]" title={c.source}>
                      {c.source}
                    </td>
                    <td className="px-2 py-1">
                      <Input
                        className="h-7"
                        value={c.name}
                        onChange={(e) => setCol(i, { name: e.target.value })}
                        aria-label={t.wizard.finalName}
                      />
                    </td>
                    <td className="px-2 py-1">
                      <div className="flex items-center gap-1">
                        <TypeIcon type={c.type} />
                        <Select
                          className="flex-1"
                          value={c.type}
                          options={TYPE_OPTIONS}
                          onChange={(type) =>
                            setCol(i, {
                              type,
                              format:
                                type === "date"
                                  ? (c.format ?? "%d/%m/%Y")
                                  : type === "datetime"
                                    ? (c.format ?? "%d/%m/%Y %H:%M:%S")
                                    : null,
                              decimal_separator:
                                (type === "decimal" || type === "integer") && fromText
                                  ? (c.decimal_separator ?? options.csv?.decimal_separator ?? ",")
                                  : null,
                            })
                          }
                          aria-label={t.common.type}
                        />
                      </div>
                    </td>
                    <td className="px-2 py-1">
                      {temporal && fromText ? (
                        <Select
                          value={c.format ?? ""}
                          placeholder="ISO"
                          options={DATE_FORMATS}
                          onChange={(format) => setCol(i, { format })}
                        />
                      ) : numeric && fromText ? (
                        <Select
                          value={c.decimal_separator ?? ""}
                          options={[
                            { value: ",", label: "1.234,56" },
                            { value: ".", label: "1,234.56" },
                          ]}
                          onChange={(decimal_separator) => setCol(i, { decimal_separator })}
                        />
                      ) : null}
                    </td>
                    <td className="max-w-56 truncate px-2 py-1 font-mono text-[11px] text-muted-foreground">
                      {guess?.examples
                        .filter((x) => x !== null)
                        .slice(0, 3)
                        .join(" · ")}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}

      {step === "done" && report && (
        <div className="flex flex-col items-center gap-3 py-6 text-center">
          <CheckCircle2 className="size-10 text-success" />
          <p className="text-[14px] font-medium">{t.wizard.done(fmtInt(report.row_count))}</p>
          {Object.entries(report.failures).map(([col, n]) => (
            <p key={col} className="rounded-md bg-warning-soft px-3 py-1.5 text-xs">
              {t.wizard.failures(col, fmtInt(n))}
            </p>
          ))}
        </div>
      )}
    </Dialog>
  );
}
