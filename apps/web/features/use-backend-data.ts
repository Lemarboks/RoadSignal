import { useEffect, useState } from "react";
import type { RoadSignalApiClient } from "../lib/api-client";
import { connectRealtimeEvents, type RealtimeEvent } from "../lib/realtime-events";
import { packagedRiskEvidence, type RiskEvidence } from "../lib/risk-evidence";
import { demoFleetAnalytics, type FleetAnalytics } from "./demo-data";
import type { AppPage } from "./operations/operations-pages";

type RealtimeStatus = "offline" | "connecting" | "connected" | "disconnected" | "unauthorized";
type BackendStatus = "unknown" | "waking" | "ready" | "unavailable";

export function useBackendData({
  apiUrl,
  apiClient,
  accessToken,
  page,
  onRealtimeEvents,
}: {
  apiUrl: string;
  apiClient: RoadSignalApiClient;
  accessToken?: string;
  page: AppPage;
  onRealtimeEvents: (events: RealtimeEvent[]) => void;
}) {
  const [realtimeStatus, setRealtimeStatus] = useState<RealtimeStatus>(apiUrl ? "connecting" : "offline");
  const [backendStatus, setBackendStatus] = useState<BackendStatus>(apiUrl ? "waking" : "unknown");
  const [riskEvidence, setRiskEvidence] = useState<RiskEvidence>(packagedRiskEvidence);
  const [riskEvidenceSource, setRiskEvidenceSource] = useState<"packaged" | "api">("packaged");
  const [fleetAnalytics, setFleetAnalytics] = useState<FleetAnalytics>(demoFleetAnalytics);
  const [fleetAnalyticsSource, setFleetAnalyticsSource] = useState<"demo" | "api">("demo");

  useEffect(() => {
    if (!apiUrl) return;
    return connectRealtimeEvents({ apiUrl, accessToken, onStatus: setRealtimeStatus, onEvents: onRealtimeEvents });
  }, [accessToken]);

  useEffect(() => {
    if (!apiUrl) return;
    let active = true;
    const controller = new AbortController();
    const timeout = window.setTimeout(() => controller.abort(), 55_000);
    setBackendStatus("waking");
    fetch(`${apiUrl}/api/v1/health`, { signal: controller.signal })
      .then((response) => { if (active) setBackendStatus(response.ok ? "ready" : "unavailable"); })
      .catch(() => { if (active) setBackendStatus("unavailable"); })
      .finally(() => window.clearTimeout(timeout));
    return () => { active = false; controller.abort(); };
  }, [apiUrl]);

  useEffect(() => {
    if (!apiUrl) return;
    let active = true;
    void apiClient.request<RiskEvidence>("/api/v1/risk/evidence")
      .then((evidence) => { if (active) { setRiskEvidence(evidence); setRiskEvidenceSource("api"); } })
      .catch(() => { if (active) setRiskEvidenceSource("packaged"); });
    return () => { active = false; };
  }, [apiClient, apiUrl]);

  useEffect(() => {
    if (!apiUrl || page !== "Analytics") return;
    let active = true;
    void apiClient.request<FleetAnalytics>("/api/v1/fleets/demo-fleet/analytics")
      .then((analytics) => { if (active) { setFleetAnalytics(analytics); setFleetAnalyticsSource("api"); } })
      .catch(() => { if (active) setFleetAnalyticsSource("demo"); });
    return () => { active = false; };
  }, [apiClient, apiUrl, page]);

  return { realtimeStatus, backendStatus, riskEvidence, riskEvidenceSource, fleetAnalytics, fleetAnalyticsSource };
}
