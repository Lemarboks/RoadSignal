import { useEffect, useState } from "react";
import type { RoadSignalApiClient } from "../lib/api-client";
import { assistantRequest, type AssistantStatus } from "../lib/assistant";
import type { MapCells, MapCellsState } from "../lib/map-cells";

export function useAssistantServices(client: RoadSignalApiClient, enabled: boolean, revision: number) {
  const [assistantStatus, setAssistantStatus] = useState<AssistantStatus | null>(null);
  const [cells, setCells] = useState<MapCellsState>({ data: null, status: enabled ? "loading" : "unavailable" });
  useEffect(() => {
    if (!enabled) return;
    const controller = new AbortController();
    const refresh = () => void assistantRequest<AssistantStatus>(client, "/api/v1/assistant/status", { signal: controller.signal }, 8_000)
      .then((value) => { if (!controller.signal.aborted) setAssistantStatus(value); })
      .catch(() => { if (!controller.signal.aborted) setAssistantStatus(null); });
    refresh();
    const timer = setInterval(refresh, 30_000);
    return () => { clearInterval(timer); controller.abort(); };
  }, [client, enabled]);
  useEffect(() => {
    if (!enabled) return;
    const controller = new AbortController();
    setCells({ data: null, status: "loading" });
    void assistantRequest<MapCells>(client, "/api/v1/map/cells?resolution=7", { signal: controller.signal }, 8_000)
      .then((data) => { if (!controller.signal.aborted) setCells({ data, status: "ready" }); })
      .catch(() => { if (!controller.signal.aborted) setCells({ data: null, status: "unavailable" }); });
    return () => controller.abort();
  }, [client, enabled, revision]);
  return { assistantStatus, cells };
}
