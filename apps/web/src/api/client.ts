import createClient from "openapi-fetch";

import type { paths } from "./generated/schema";
import type { ApiErrorBody, Issue } from "./types";

export const API_BASE: string = (import.meta.env.VITE_API_URL as string | undefined) ?? "/api";

export const api = createClient<paths>({ baseUrl: API_BASE });

/** Fired on any 401 (session expired or logged out elsewhere): the app shows the login screen. */
export const UNAUTHENTICATED_EVENT = "forja:unauthenticated";

function signal401(status: number) {
  if (status === 401) window.dispatchEvent(new Event(UNAUTHENTICATED_EVENT));
}

/** Error carrying the backend's pt-BR message and issues. */
export class ApiError extends Error {
  readonly code: string;
  readonly hint: string | null;
  readonly detail: string | null;
  readonly issues: Issue[];
  readonly status: number;

  constructor(body: Partial<ApiErrorBody> | undefined, status: number) {
    super(body?.message ?? "Não foi possível falar com o servidor.");
    this.code = body?.code ?? "NETWORK";
    this.hint = body?.hint ?? null;
    this.detail = body?.detail ?? null;
    this.issues = body?.issues ?? [];
    this.status = status;
  }
}

/** An ApiError shown with the same component as server issues. */
export function errorIssue(e: unknown): Issue {
  const err = e instanceof ApiError ? e : new ApiError(undefined, 0);
  return {
    code: err.code as Issue["code"],
    message: err.message,
    hint: err.hint,
    detail: err.detail,
    severity: "error",
  };
}

/** Unwrap an openapi-fetch result, throwing ApiError on failure. */
export function unwrap<T>(res: { data?: T; error?: unknown; response: Response }): T {
  if (res.error !== undefined || !res.response.ok) {
    signal401(res.response.status);
    throw new ApiError(res.error as Partial<ApiErrorBody> | undefined, res.response.status);
  }
  return res.data as T;
}

export async function postRaw(path: string, body: unknown, signal?: AbortSignal): Promise<Response> {
  const res = await fetch(`${API_BASE}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
    signal,
  });
  if (!res.ok) {
    signal401(res.status);
    let parsed: Partial<ApiErrorBody> | undefined;
    try {
      parsed = (await res.json()) as Partial<ApiErrorBody>;
    } catch {
      parsed = undefined;
    }
    throw new ApiError(parsed, res.status);
  }
  return res;
}

/** Multipart upload with progress (fetch has no upload progress). */
export function uploadWithProgress<T>(
  path: string,
  form: FormData,
  onProgress: (fraction: number) => void,
): Promise<T> {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open("POST", `${API_BASE}${path}`);
    xhr.upload.onprogress = (e) => {
      if (e.lengthComputable) onProgress(e.loaded / e.total);
    };
    xhr.onload = () => {
      let body: unknown;
      try {
        body = JSON.parse(xhr.responseText);
      } catch {
        body = undefined;
      }
      if (xhr.status >= 200 && xhr.status < 300) resolve(body as T);
      else {
        signal401(xhr.status);
        reject(new ApiError(body as Partial<ApiErrorBody> | undefined, xhr.status));
      }
    };
    xhr.onerror = () => reject(new ApiError(undefined, 0));
    xhr.send(form);
  });
}
