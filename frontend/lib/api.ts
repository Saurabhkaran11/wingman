/** The only place that talks to the FastAPI backend. */

import type { Dossier, Health, Meeting, RunSummary, SavedDossier } from "./types";

/**
 * Empty in production: the static export is served by FastAPI itself, so the API
 * is same-origin. In `npm run dev` the frontend is on :3000 and the API on :8000,
 * so NEXT_PUBLIC_API_BASE points at the backend (see .env.development).
 */
export const API_BASE = process.env.NEXT_PUBLIC_API_BASE ?? "";

export class ApiError extends Error {
  constructor(message: string, readonly status: number) {
    super(message);
    this.name = "ApiError";
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${API_BASE}${path}`, {
      ...init,
      headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) },
    });
  } catch {
    // A network-level failure means the backend is not running at all.
    throw new ApiError("Cannot reach the Wingman server. Is `wingman web` running?", 0);
  }
  if (!response.ok) {
    let detail = `${response.status} ${response.statusText}`;
    try {
      const body = (await response.json()) as { detail?: string };
      if (body.detail) detail = body.detail;
    } catch {
      /* keep the status line */
    }
    throw new ApiError(detail, response.status);
  }
  return response.status === 204 ? (null as T) : ((await response.json()) as T);
}

export const api = {
  health: () => request<Health>("/api/health"),

  meetings: () => request<{ source: string; meetings: Meeting[] }>("/api/meetings"),

  dossiers: () => request<{ dossiers: SavedDossier[] }>("/api/dossiers"),

  dossier: (slug: string) => request<Dossier>(`/api/dossiers/${encodeURIComponent(slug)}`),

  pdfUrl: (slug: string) => `${API_BASE}/api/dossiers/${encodeURIComponent(slug)}/pdf`,

  /** 202 with a run id; watch it with streamUrl(). 409 means one is already going. */
  startBrief: (body: { person?: string; company?: string; writeback?: boolean }) =>
    request<{ run: string; title: string }>("/api/brief", {
      method: "POST",
      body: JSON.stringify({ person: "", company: "", writeback: true, ...body }),
    }),

  activeRun: () => request<{ run: RunSummary | null }>("/api/runs"),

  run: (id: string) => request<RunSummary>(`/api/runs/${encodeURIComponent(id)}`),

  streamUrl: (id: string) => `${API_BASE}/api/runs/${encodeURIComponent(id)}/stream`,
};

/** Only http(s) URLs are ever rendered as links: scraped text is untrusted. */
export function safeUrl(value: string): string | null {
  try {
    const url = new URL(value);
    return url.protocol === "https:" || url.protocol === "http:" ? url.href : null;
  } catch {
    return null;
  }
}
