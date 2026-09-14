import { useEffect, useRef, useState } from "react";
import type { RoadSignalApiClient } from "../../lib/api-client";
import { assistantError, assistantRequest, type RouteExplanation } from "../../lib/assistant";

export function RouteAssistant({ client, routeId, canExplain }: {
  client: RoadSignalApiClient; routeId: string; canExplain: boolean;
}) {
  const [result, setResult] = useState<RouteExplanation | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const request = useRef<AbortController | null>(null);
  useEffect(() => () => request.current?.abort(), []);
  async function explain() {
    request.current?.abort();
    const controller = new AbortController();
    request.current = controller;
    setBusy(true);
    setError("");
    try {
      const response = await assistantRequest<RouteExplanation>(client,
        `/api/v1/assistant/routes/${encodeURIComponent(routeId)}/explain`,
        { method: "POST", signal: controller.signal });
      if (!controller.signal.aborted) setResult(response);
    } catch (failure) {
      if (!controller.signal.aborted) setError(assistantError(failure));
    } finally {
      if (!controller.signal.aborted) setBusy(false);
    }
  }
  return (
    <div className="route-assistant">
      <div className="assistant-actions">
        <button type="button" disabled={!canExplain || busy} onClick={() => void explain()}>
          {busy ? "Checking route evidence…" : "Explain route evidence"}
        </button>
        {!canExplain && <span>Sign in and find routes to request an evidence summary.</span>}
      </div>
      {error && <p className="assistant-error" role="alert">{error} The route explanation above remains available.</p>}
      {result && (
        <section aria-label="Route evidence summary" aria-live="polite">
          <p className="assistant-caption">{result.mode === "model" ? "AI-assisted summary · review the supporting evidence" : "Evidence summary · generated from route data"}</p>
          <p>{result.summary}</p>
          <dl className="assistant-evidence">
            {result.evidence.map((item) => (
              <div key={item.id}><dt>{item.label}</dt><dd>{item.value}<small>Source: {item.id}</small></dd></div>
            ))}
          </dl>
          {result.warnings.map((warning) => <p className="assistant-caption" key={warning}>{warning}</p>)}
        </section>
      )}
    </div>
  );
}
