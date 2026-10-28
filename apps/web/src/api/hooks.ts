import {
  keepPreviousData,
  useInfiniteQuery,
  useMutation,
  useQuery,
  useQueryClient,
} from "@tanstack/react-query";
import { tableFromIPC, type Table } from "apache-arrow";

import { api, postRaw, unwrap, uploadWithProgress } from "./client";
import type {
  Column,
  ConfirmOut,
  Detection,
  ExportJob,
  FormulaCheck,
  ImportOptions,
  Pipeline,
  Project,
  SchemaResponse,
  Source,
  StatsOut,
  UploadOut,
} from "./types";

/**
 * Key of the parts of the pipeline that affect data. Moving nodes around the
 * canvas must not refetch schemas or previews.
 */
export function semanticKey(p: Pipeline): string {
  return JSON.stringify({
    s: p.settings,
    n: p.nodes.map((n) => [n.id, n.type, n.config, n.ui?.label ?? null]),
    e: p.edges.map((e) => [e.source, e.target, e.source_handle, e.target_handle]),
  });
}

/* ---------------------------------------------------------------- projects */

export function useProjects() {
  return useQuery({
    queryKey: ["projects"],
    queryFn: async () => unwrap(await api.GET("/projects")),
  });
}

export function useProject(id: string) {
  return useQuery({
    queryKey: ["project", id],
    queryFn: async () =>
      unwrap(await api.GET("/projects/{project_id}", { params: { path: { project_id: id } } })),
  });
}

export function useCreateProject() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (name: string): Promise<Project> =>
      unwrap(await api.POST("/projects", { body: { name } })),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["projects"] }),
  });
}

export function useRenameProject() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async ({ id, name }: { id: string; name: string }) =>
      unwrap(
        await api.PATCH("/projects/{project_id}", { params: { path: { project_id: id } }, body: { name } }),
      ),
    onSuccess: (p) => {
      void qc.invalidateQueries({ queryKey: ["projects"] });
      qc.setQueryData(["project", p.id], p);
    },
  });
}

export function useDeleteProject() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (id: string) => {
      unwrap(await api.DELETE("/projects/{project_id}", { params: { path: { project_id: id } } }));
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ["projects"] }),
  });
}

export async function loadPipeline(id: string) {
  return unwrap(await api.GET("/projects/{project_id}/pipeline", { params: { path: { project_id: id } } }));
}

export async function savePipeline(id: string, pipeline: Pipeline) {
  return unwrap(
    await api.PUT("/projects/{project_id}/pipeline", {
      params: { path: { project_id: id } },
      body: pipeline,
    }),
  );
}

/* ---------------------------------------------------------------- pipeline */

export function useSchema(pipeline: Pipeline) {
  const key = semanticKey(pipeline);
  return useQuery({
    queryKey: ["schema", key],
    queryFn: async ({ signal }): Promise<SchemaResponse> =>
      unwrap(await api.POST("/pipeline/schema", { body: { pipeline }, signal })),
    placeholderData: keepPreviousData,
    staleTime: Infinity,
  });
}

export interface PreviewPage {
  table: Table;
  rows: number;
  hasMore: boolean;
}

export const PAGE_SIZE = 500;

/** Preview pages of a node. Keyed by the node hash: editing downstream nodes keeps this cache. */
export function usePreview(pipeline: Pipeline, nodeId: string | null, hash: string | null | undefined) {
  return useInfiniteQuery({
    queryKey: ["preview", hash, nodeId],
    enabled: nodeId !== null && Boolean(hash),
    initialPageParam: 0,
    queryFn: async ({ pageParam, signal }): Promise<PreviewPage> => {
      const res = await postRaw(
        "/pipeline/preview",
        { pipeline, node_id: nodeId, limit: PAGE_SIZE, offset: pageParam },
        signal,
      );
      const buf = await res.arrayBuffer();
      return {
        table: tableFromIPC(new Uint8Array(buf)),
        rows: Number(res.headers.get("X-Forja-Rows") ?? "0"),
        hasMore: res.headers.get("X-Forja-Has-More") === "1",
      };
    },
    getNextPageParam: (last, pages) => (last.hasMore ? pages.length * PAGE_SIZE : undefined),
    staleTime: Infinity,
    retry: false,
  });
}

/** Row counts and data-dependent warnings of a node (background, after the preview). */
export function useStats(pipeline: Pipeline, nodeId: string | null, hash: string | null | undefined) {
  return useQuery({
    queryKey: ["stats", hash, nodeId],
    enabled: nodeId !== null && Boolean(hash),
    queryFn: async ({ signal }) =>
      unwrap(await api.POST("/pipeline/stats", { body: { pipeline, node_id: nodeId ?? "" }, signal })),
    staleTime: Infinity,
    retry: false,
  });
}

/** Cached stats only (never fetches): used by node cards to show row counts. */
export function useCachedStats(nodeId: string, hash: string | null | undefined): StatsOut | undefined {
  return useQuery<StatsOut>({
    queryKey: ["stats", hash, nodeId],
    enabled: false,
    queryFn: () => Promise.reject(new Error("cache only")),
    staleTime: Infinity,
  }).data;
}

export function useProfile(
  pipeline: Pipeline,
  nodeId: string | null,
  hash: string | null | undefined,
  column: string | null,
) {
  return useQuery({
    queryKey: ["profile", hash, nodeId, column],
    enabled: nodeId !== null && column !== null && Boolean(hash),
    queryFn: async ({ signal }) =>
      unwrap(
        await api.POST("/pipeline/profile", {
          body: { pipeline, node_id: nodeId ?? "", column: column ?? "" },
          signal,
        }),
      ),
    staleTime: Infinity,
    retry: false,
  });
}

export function useDistinctValues(pipeline: Pipeline, nodeId: string, column: string | null, ofInput = true) {
  const key = semanticKey(pipeline);
  return useQuery({
    queryKey: ["distinct", key, nodeId, column, ofInput],
    enabled: column !== null && column !== "",
    queryFn: async ({ signal }) =>
      unwrap(
        await api.POST("/pipeline/distinct-values", {
          body: {
            pipeline,
            node_id: nodeId,
            column: column ?? "",
            limit: 200,
            of_input: ofInput,
            date_group: "none",
            as_text: false,
          },
          signal,
        }),
      ),
    staleTime: Infinity,
    retry: false,
  });
}

/** Distinct values as the pivot compiles them (text, optional date grouping). */
export async function fetchPivotValues(
  pipeline: Pipeline,
  nodeId: string,
  column: string,
  dateGroup: "none" | "year" | "quarter" | "month" | "day",
) {
  return unwrap(
    await api.POST("/pivot/distinct-values", {
      body: {
        pipeline,
        node_id: nodeId,
        column,
        limit: 201,
        of_input: true,
        date_group: dateGroup,
        as_text: true,
      },
    }),
  );
}

export async function fetchSql(pipeline: Pipeline, nodeId: string): Promise<string> {
  return unwrap(await api.POST("/pipeline/sql", { body: { pipeline, node_id: nodeId } })).sql;
}

/* ---------------------------------------------------------------- formulas */

export function useFunctions() {
  return useQuery({
    queryKey: ["functions"],
    queryFn: async () => unwrap(await api.GET("/formula/functions")),
    staleTime: Infinity,
  });
}

export async function checkFormula(
  body: {
    formula: string;
    locale: "pt-BR" | "en-US";
    context?: "row" | "aggregate";
    group_keys?: string[];
    pipeline?: Pipeline;
    node_id?: string;
    columns?: Column[];
  },
  signal?: AbortSignal,
): Promise<FormulaCheck> {
  return unwrap(
    await api.POST("/formula/check", { body: { context: "row", group_keys: [], ...body }, signal }),
  );
}

export async function renderFormula(formula: string, from: "pt-BR" | "en-US", to: "pt-BR" | "en-US") {
  return unwrap(await api.POST("/formula/render", { body: { formula, from_locale: from, to_locale: to } }));
}

/* ---------------------------------------------------------------- sources */

export function useSources(projectId: string | null) {
  return useQuery({
    queryKey: ["sources", projectId],
    queryFn: async () =>
      unwrap(await api.GET("/sources", { params: { query: projectId ? { project_id: projectId } : {} } })),
  });
}

export function uploadSource(file: File, projectId: string | null, onProgress: (f: number) => void) {
  const form = new FormData();
  form.append("file", file);
  if (projectId) form.append("project_id", projectId);
  return uploadWithProgress<UploadOut>("/sources", form, onProgress);
}

export function replaceSourceFile(sourceId: string, file: File, onProgress: (f: number) => void) {
  const form = new FormData();
  form.append("file", file);
  return uploadWithProgress<UploadOut>(`/sources/${sourceId}/replace`, form, onProgress);
}

export async function redetect(sourceId: string, options: ImportOptions): Promise<Detection> {
  return unwrap(
    await api.POST("/sources/{source_id}/detect", {
      params: { path: { source_id: sourceId } },
      body: { options },
    }),
  );
}

export async function getDetection(sourceId: string): Promise<Detection> {
  return unwrap(
    await api.GET("/sources/{source_id}/detection", { params: { path: { source_id: sourceId } } }),
  );
}

export async function confirmImport(sourceId: string, options: ImportOptions): Promise<ConfirmOut> {
  return unwrap(
    await api.POST("/sources/{source_id}/confirm", {
      params: { path: { source_id: sourceId } },
      body: options,
    }),
  );
}

export function useDeleteSource() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (id: string) => {
      unwrap(await api.DELETE("/sources/{source_id}", { params: { path: { source_id: id } } }));
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ["sources"] }),
  });
}

export function sourceById(sources: Source[] | undefined, id: string | undefined): Source | undefined {
  return sources?.find((s) => s.id === id);
}

/* ---------------------------------------------------------------- exports */

export async function startExport(
  pipeline: Pipeline,
  nodeId: string,
  projectId: string | null,
): Promise<ExportJob> {
  return unwrap(await api.POST("/exports", { body: { pipeline, node_id: nodeId, project_id: projectId } }));
}

export function useExportJob(jobId: string | null) {
  return useQuery({
    queryKey: ["export", jobId],
    enabled: jobId !== null,
    queryFn: async () =>
      unwrap(await api.GET("/exports/{job_id}", { params: { path: { job_id: jobId ?? "" } } })),
    refetchInterval: (q) => {
      const s = q.state.data?.status;
      return s === "done" || s === "error" ? false : 500;
    },
  });
}

export function exportDownloadUrl(jobId: string): string {
  return `${import.meta.env.VITE_API_URL ?? "/api"}/exports/${jobId}/download`;
}
