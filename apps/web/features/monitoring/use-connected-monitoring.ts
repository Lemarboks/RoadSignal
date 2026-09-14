"use client";
import { useCallback, useEffect, useMemo, useState } from "react";
import { ApiError, type RoadSignalApiClient } from "../../lib/api-client";
import { assistantRequest } from "../../lib/assistant";
import { connectedReadings, validateMonitoringSnapshot, type MonitoringSnapshot } from "../../lib/connected-monitoring";

export function useConnectedMonitoring(client: RoadSignalApiClient, enabled: boolean) {
  const [accepted, setAccepted] = useState<{ snapshot: MonitoringSnapshot; at: number } | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [now, setNow] = useState(0);
  const [attempt, setAttempt] = useState(0);
  const retry = useCallback(() => setAttempt((value) => value + 1), []);
  useEffect(() => {
    if (!enabled) return;
    let disposed = false, timer: ReturnType<typeof setTimeout>;
    const controller = new AbortController();
    const poll = async () => {
      setLoading(true);
      try {
        const result = await assistantRequest<unknown>(client, "/api/v1/monitoring", { signal: controller.signal }, 8_000);
        const snapshot = validateMonitoringSnapshot(result);
        if (!disposed) { const at = Date.now(); setAccepted({ snapshot, at }); setNow(at); setError(null); }
      } catch (cause) {
        if (!disposed) setError(cause instanceof ApiError && [401, 403].includes(cause.status)
          ? "Sign in to access connected monitoring. Guest replay is still available."
          : "Connection lost. Check the monitoring API, then retry. Any retained readings are not current.");
      } finally {
        if (!disposed) { setLoading(false); timer = setTimeout(() => { if (!document.hidden) void poll(); }, 5_000); }
      }
    };
    const resume = () => { if (!document.hidden) { clearTimeout(timer); controller.signal.aborted || void poll(); } };
    void poll();
    document.addEventListener("visibilitychange", resume);
    return () => { disposed = true; controller.abort(); clearTimeout(timer); document.removeEventListener("visibilitychange", resume); };
  }, [client, enabled, attempt]);
  useEffect(() => {
    if (!enabled) return;
    const timer = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(timer);
  }, [enabled]);
  const readings = useMemo(() => connectedReadings(accepted?.snapshot ?? null, accepted ? Math.max(0, now - accepted.at) / 1000 : 0, !!error), [accepted, now, error]);
  return { ...readings, snapshot: accepted?.snapshot ?? null, error, loading, retry };
}
