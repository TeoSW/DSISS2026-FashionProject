import type {
  Analysis,
  FeedbackResult,
  FeedbackStats,
  GarmentQuery,
  GraphStats,
  Health,
  Insights,
  Ontology,
  WardrobeResponse,
} from "./types";

// One place that knows where the backend is. Everything else asks this module.
export const BASE = (
  import.meta.env.VITE_API_URL ?? "http://localhost:8000"
).replace(/\/+$/, "");

export const MAX_UPLOAD = 12 * 1024 * 1024; // must match MAX_UPLOAD in api.py

/**
 * FastAPI phrases its errors for a person to read and puts them in `detail`.
 * Surfacing that string unchanged is the whole error strategy: the server
 * already knows what went wrong, and rewriting it here would only add a second,
 * vaguer version of the same sentence.
 */
export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
    this.name = "ApiError";
  }
}

async function unwrap<T>(res: Response): Promise<T> {
  if (res.ok) return (await res.json()) as T;

  let detail = `${res.status} ${res.statusText}`;
  try {
    const body = await res.json();
    if (typeof body.detail === "string") detail = body.detail;
    else if (Array.isArray(body.detail) && body.detail[0]?.msg)
      detail = body.detail.map((d: { msg: string }) => d.msg).join("; ");
  } catch {
    // a non-JSON error body: keep the status line
  }
  throw new ApiError(res.status, detail);
}

async function get<T>(path: string, signal?: AbortSignal): Promise<T> {
  return unwrap<T>(await fetch(`${BASE}${path}`, { signal }));
}

export const health = (signal?: AbortSignal) => get<Health>("/health", signal);
export const ontology = (signal?: AbortSignal) => get<Ontology>("/ontology", signal);
export const graphStats = (signal?: AbortSignal) => get<GraphStats>("/stats", signal);
export const feedbackStats = (signal?: AbortSignal) =>
  get<FeedbackStats>("/feedback/stats", signal);

export async function analyze(file: File, save: boolean): Promise<Analysis> {
  const form = new FormData();
  form.append("file", file);
  form.append("save", String(save));
  form.append("cutout", "true");
  return unwrap<Analysis>(
    await fetch(`${BASE}/analyze`, { method: "POST", body: form })
  );
}

export async function sendFeedback(body: {
  analysis_id: string;
  verdict: "correct" | "wrong";
  corrections: Record<string, string>;
  note: string;
}): Promise<FeedbackResult> {
  return unwrap<FeedbackResult>(
    await fetch(`${BASE}/feedback`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    })
  );
}

export async function garments(
  group: string,
  value: string
): Promise<GarmentQuery> {
  const query = new URLSearchParams({ [group]: value });
  return get<GarmentQuery>(`/garments?${query}`);
}

export const insights = (signal?: AbortSignal) => get<Insights>("/insights", signal);

export function wardrobe(
  region?: string | null,
  signal?: AbortSignal
): Promise<WardrobeResponse> {
  const query = region ? `?region=${encodeURIComponent(region)}` : "";
  return get<WardrobeResponse>(`/wardrobe${query}`, signal);
}

/** The stored cutout. Relative in the API response, absolute for an <img src>. */
export const photoUrl = (path: string) => `${BASE}${path}`;

export async function deleteGarment(id: string): Promise<{ deleted: string }> {
  return unwrap<{ deleted: string }>(
    await fetch(`${BASE}/garments/${encodeURIComponent(id)}`, { method: "DELETE" })
  );
}
