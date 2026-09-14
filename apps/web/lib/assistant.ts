import type { Coordinate, Incident } from "@roadsignal/types";
import type { RoadSignalApiClient } from "./api-client";

type Capability = { configured: boolean; available: boolean; model: string | null };
export type AssistantStatus = {
  generation: Capability;
  retrieval: Capability;
  reranker: Capability;
  transcription: Capability;
  notice: string;
};
export type IncidentDraft = { incident_type: string; severity: number; description: string };
export type IncidentAnalysis = {
  mode: "model" | "fallback";
  retrieval_mode: "semantic" | "lexical" | "unavailable";
  draft: IncidentDraft;
  duplicates: { id: string; incident_type: string; description: string; distance_km: number | null; similarity: number; occurred_at: string }[];
  warnings: string[];
  requires_review: true;
};
export type RouteExplanation = {
  mode: "model" | "fallback";
  summary: string;
  evidence: { id: string; label: string; value: string }[];
  warnings: string[];
  score_unchanged: true;
};
export type IncidentReport = IncidentDraft & { location: Coordinate };
export type ApiIncident = {
  id: string; incident_type: string; severity: number; source_type: string;
  verification_status: string; confidence: number; description: string;
  occurred_at: string; expires_at: string | null; location: Coordinate;
  confirmations: number; disputes: number; status: Incident["status"];
};
export function fromApiIncident(item: ApiIncident): Incident {
  return {
    id: item.id, incidentType: item.incident_type, severity: item.severity,
    sourceType: item.source_type, verificationStatus: item.verification_status,
    confidence: item.confidence, description: item.description,
    occurredAt: item.occurred_at, expiresAt: item.expires_at, location: item.location,
    confirmations: item.confirmations, disputes: item.disputes, status: item.status,
  };
}

export async function assistantRequest<T>(
  client: RoadSignalApiClient,
  path: string,
  init: RequestInit = {},
  timeoutMs = 150_000,
): Promise<T> {
  const controller = new AbortController();
  const abort = () => controller.abort();
  if (init.signal?.aborted) controller.abort();
  init.signal?.addEventListener("abort", abort, { once: true });
  const timer = setTimeout(abort, timeoutMs);
  try {
    return await client.request<T>(path, { ...init, signal: controller.signal });
  } finally {
    clearTimeout(timer);
    init.signal?.removeEventListener("abort", abort);
  }
}

export function assistantError(error: unknown) {
  return error instanceof Error && error.name !== "AbortError"
    ? error.message
    : "The request took too long. Please try again.";
}
