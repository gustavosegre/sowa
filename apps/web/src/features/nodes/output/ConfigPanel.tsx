import { Download, Play } from "lucide-react";
import { useState } from "react";

import { ApiError, errorIssue } from "@/api/client";
import { downloadExport, startExport, useExportJob } from "@/api/hooks";
import type { OutputConfig } from "@/api/types";
import { IssueItem } from "@/components/IssueList";
import { Button, Field, Input, Select, Spinner, Switch } from "@/components/ui";
import { useProjectId } from "@/features/editor/project";
import { t } from "@/i18n/pt-BR";
import { fmtBytes, fmtInt } from "@/lib/utils";
import { usePipelineStore } from "@/stores/pipelineStore";

import { ColumnMultiSelect } from "../shared/ColumnSelect";
import type { ConfigPanelProps } from "../shared/panel";

function ExportButton({ nodeId }: { nodeId: string }) {
  const projectId = useProjectId();
  const [jobId, setJobId] = useState<string | null>(null);
  const [error, setError] = useState<ApiError | null>(null);
  const [starting, setStarting] = useState(false);
  const { data: job } = useExportJob(jobId);
  const tt = t.nodes.output;
  const running = starting || job?.status === "pending" || job?.status === "running";

  const run = async () => {
    setError(null);
    setStarting(true);
    try {
      const pipeline = usePipelineStore.getState().pipeline;
      const j = await startExport(pipeline, nodeId, projectId);
      setJobId(j.id);
    } catch (e) {
      setError(e instanceof ApiError ? e : new ApiError(undefined, 0));
    } finally {
      setStarting(false);
    }
  };

  return (
    <div className="flex flex-col gap-2 border-t pt-3">
      <Button onClick={() => void run()} disabled={running}>
        {running ? <Spinner /> : <Play />}
        {running ? tt.exporting : tt.export}
      </Button>
      {running && job && (
        <div
          className="h-1.5 overflow-hidden rounded-full bg-muted"
          role="progressbar"
          aria-valuenow={job.progress * 100}
        >
          <div
            className="h-full bg-primary transition-all"
            style={{ width: `${Math.max(5, job.progress * 100)}%` }}
          />
        </div>
      )}
      {job?.status === "done" && (
        <div className="flex flex-col gap-1.5 rounded-md border bg-muted/50 p-2">
          <p className="text-xs">{tt.done(fmtInt(job.rows), fmtBytes(job.size_bytes ?? 0))}</p>
          <Button
            variant="outline"
            size="sm"
            onClick={() =>
              void downloadExport(job.id).catch((e: unknown) =>
                setError(e instanceof ApiError ? e : new ApiError(undefined, 0)),
              )
            }
          >
            <Download /> {tt.download}
          </Button>
        </div>
      )}
      {job?.status === "error" && job.error && <IssueItem issue={job.error} />}
      {error && <IssueItem issue={errorIssue(error)} />}
    </div>
  );
}

export function ConfigPanel({ node, config, update, columns }: ConfigPanelProps<OutputConfig>) {
  const tt = t.nodes.output;
  const csv = config.csv;
  const custom = config.format === "csv" && config.preset !== "excel_br";
  const setCsv = (patch: Partial<OutputConfig["csv"]>) => update({ ...config, csv: { ...csv, ...patch } });
  return (
    <div className="flex flex-col gap-3">
      <div className="grid grid-cols-[1fr_auto] gap-2">
        <Field label={tt.filename}>
          <Input value={config.filename} onChange={(e) => update({ ...config, filename: e.target.value })} />
        </Field>
        <Field label={tt.format}>
          <Select
            value={config.format}
            options={[
              { value: "csv", label: "CSV" },
              { value: "parquet", label: "Parquet" },
              { value: "xlsx", label: "XLSX (Excel)" },
              { value: "json", label: "JSON" },
              { value: "ndjson", label: "NDJSON" },
            ]}
            onChange={(format) => update({ ...config, format })}
          />
        </Field>
      </div>
      {config.format === "csv" && (
        <Field label={tt.preset}>
          <Select
            value={config.preset ?? "custom"}
            options={[
              { value: "excel_br", label: tt.presetExcelBr },
              { value: "custom", label: tt.presetCustom },
            ]}
            onChange={(preset) => update({ ...config, preset })}
          />
        </Field>
      )}
      {custom && (
        <div className="grid grid-cols-2 gap-2">
          <Field label={tt.delimiter}>
            <Select
              value={csv.delimiter}
              options={Object.entries(t.wizard.delimiters).map(([value, label]) => ({ value, label }))}
              onChange={(delimiter) => setCsv({ delimiter })}
            />
          </Field>
          <Field label={tt.encoding}>
            <Select
              value={csv.encoding}
              options={[
                { value: "utf-8", label: "UTF-8" },
                { value: "utf-8-sig", label: "UTF-8 com BOM" },
                { value: "latin-1", label: "Windows-1252 / Latin-1" },
              ]}
              onChange={(encoding) => setCsv({ encoding })}
            />
          </Field>
          <Field label={tt.decimal}>
            <Select
              value={csv.decimal_separator}
              options={[
                { value: ".", label: "Ponto (1.5)" },
                { value: ",", label: "Vírgula (1,5)" },
              ]}
              onChange={(decimal_separator) => setCsv({ decimal_separator })}
            />
          </Field>
          <Field label={tt.dateFormat}>
            <Select
              value={csv.date_format}
              options={[
                { value: "%Y-%m-%d", label: "aaaa-mm-dd" },
                { value: "%d/%m/%Y", label: "dd/mm/aaaa" },
                { value: "%m/%d/%Y", label: "mm/dd/aaaa" },
              ]}
              onChange={(date_format) => setCsv({ date_format, datetime_format: `${date_format} %H:%M:%S` })}
            />
          </Field>
          <div className="col-span-2">
            <Switch checked={csv.header} onCheckedChange={(header) => setCsv({ header })} label={tt.header} />
          </div>
        </div>
      )}
      {config.format === "parquet" && (
        <div className="grid grid-cols-2 gap-2">
          <Field label={tt.compression}>
            <Select
              value={config.parquet.compression}
              options={[
                { value: "zstd", label: "zstd" },
                { value: "snappy", label: "snappy" },
                { value: "none", label: "nenhuma" },
              ]}
              onChange={(compression) => update({ ...config, parquet: { ...config.parquet, compression } })}
            />
          </Field>
          <Field label={tt.rowGroup}>
            <Input
              type="number"
              placeholder="padrão"
              value={config.parquet.row_group_size ?? ""}
              onChange={(e) =>
                update({
                  ...config,
                  parquet: {
                    ...config.parquet,
                    row_group_size: e.target.value ? Number(e.target.value) : null,
                  },
                })
              }
            />
          </Field>
        </div>
      )}
      {config.format === "parquet" && (
        <Field label={t.partition}>
          <ColumnMultiSelect
            columns={columns}
            value={config.parquet.partition_by}
            onChange={(partition_by) => update({ ...config, parquet: { ...config.parquet, partition_by } })}
          />
        </Field>
      )}
      <ExportButton nodeId={node.id} />
    </div>
  );
}
