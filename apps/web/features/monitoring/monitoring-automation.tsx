"use client";
import { useEffect, useState } from "react";
import type { RoadSignalApiClient, SessionSnapshot } from "../../lib/api-client";
import { assistantError, assistantRequest } from "../../lib/assistant";
import { evidenceSourceUrl, timestampLabel, type EvidenceItem, type MonitoringSnapshot } from "../../lib/connected-monitoring";
import { TrafficFrameCheck } from "./traffic-frame-check";
import { deployment } from "../../lib/deployment";

type DailyReport = { run_key: string; started_at: string; source: "demo";
  summary: { devices_total: number; fresh_devices: number; stale_devices: number; open_alerts: number } };

export function MonitoringAutomation({ client, session, snapshot, connectionLost }: {
  client: RoadSignalApiClient; session: SessionSnapshot | null; snapshot: MonitoringSnapshot | null; connectionLost: boolean;
}) {
  const [items, setItems] = useState<EvidenceItem[] | null>(null);
  const [notes, setNotes] = useState<Record<string, string>>({});
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [reports, setReports] = useState<DailyReport[] | null>(null);
  const [reportError, setReportError] = useState<string | null>(null);
  const canReview = !!session?.accessToken && ["administrator", "incident_moderator"].includes(session.user.role);
  useEffect(() => { setItems(null); setReports(null); setReportError(null); setNotes({}); setError(null); setNotice(null); }, [session?.user.id]);
  async function loadReports() {
    setBusy("reports"); setReportError(null);
    try {
      const result = await assistantRequest<{ items: DailyReport[] }>(client, "/api/v1/monitoring/reports", {}, 10_000);
      setReports(result.items);
    } catch (cause) { setReportError(assistantError(cause)); }
    finally { setBusy(null); }
  }
  async function loadInbox() {
    setBusy("inbox"); setError(null); setNotice(null);
    try {
      const result = await assistantRequest<{ items: EvidenceItem[] }>(client, "/api/v1/monitoring/evidence?status=pending&limit=100", {}, 10_000);
      setItems(result.items);
    } catch (cause) { setError(assistantError(cause)); }
    finally { setBusy(null); }
  }
  async function decide(item: EvidenceItem, decision: "approved" | "rejected") {
    const note = notes[item.id]?.trim() ?? "";
    if (!canReview || note.length < 3 || busy) return;
    setBusy(item.id); setError(null); setNotice(null);
    try {
      await assistantRequest<EvidenceItem>(client, `/api/v1/monitoring/evidence/${encodeURIComponent(item.id)}/decision`, {
        method: "POST", body: JSON.stringify({ decision, note }),
      }, 10_000);
      setItems((previous) => previous?.filter((entry) => entry.id !== item.id) ?? null);
      setNotice(`Evidence ${decision}. No incident was published and route scores are unchanged.`);
    } catch (cause) { setError(assistantError(cause)); }
    finally { setBusy(null); }
  }
  const alerts = snapshot?.alerts.filter((item) => item.status === "open") ?? [];
  return <section className="monitor-automation" aria-label="Monitoring automation">
    <header><div><h3>Automation & review</h3><p>Device health checks and a separate evidence review queue.</p></div>
      <span className="demo-source-label">No automatic incident publication</span></header>
    <dl className="automation-facts">
      <div><dt>Automation access</dt><dd>{snapshot ? snapshot.automation.configured ? "Configured" : "Not configured" : "Not checked"}</dd></div>
      <div><dt>Last recorded automation run</dt><dd>{timestampLabel(snapshot?.automation.last_run_at ?? null)}</dd></div>
      <div><dt>Recorded runs</dt><dd>{snapshot ? snapshot.automation.run_count : "Unavailable"}</dd></div>
    </dl>
    {connectionLost && <p className="automation-notice">Connection lost. Automation status and alerts below are from the last accepted snapshot, if available.</p>}
    <div className="automation-alerts"><h4>Open device alerts</h4>
      {alerts.length ? <ul>{alerts.map((alert) => <li key={alert.id}><strong>{alert.device_id}</strong><span>{alert.message}</span><small>Demo · opened {timestampLabel(alert.opened_at)}</small></li>)}</ul>
        : <p>{snapshot ? "No open alerts in the last accepted snapshot." : "Alerts have not been received."}</p>}
    </div>
    <details className="daily-reports"><summary>Saved daily summaries</summary>
      <p>n8n saves a demo fleet summary at 07:00 Johannesburg time. The latest 31 daily reports are retained separately from minute-by-minute checks.</p>
      {!canReview ? <p>Sign in as an incident moderator or administrator to view saved reports.</p> : <>
        <button type="button" disabled={!!busy} onClick={() => void loadReports()}>{busy === "reports" ? "Loading reports…" : reports ? "Refresh saved reports" : "Load saved reports"}</button>
        {reportError && <p role="alert" className="automation-error">{reportError}</p>}
        {reports?.length === 0 && <p>No daily report has run yet. Use the daily workflow's Manual test in n8n, or wait for its schedule.</p>}
        {!!reports?.length && <div className="daily-report-scroll"><table><caption>Synthetic device summaries · not real traffic statistics</caption>
          <thead><tr><th scope="col">Recorded</th><th scope="col">Devices</th><th scope="col">Fresh</th><th scope="col">Stale</th><th scope="col">Alerts</th></tr></thead>
          <tbody>{reports.map(report => <tr key={report.run_key}><th scope="row">{timestampLabel(report.started_at)}</th>
            <td>{report.summary.devices_total}</td><td>{report.summary.fresh_devices}</td><td>{report.summary.stale_devices}</td><td>{report.summary.open_alerts}</td></tr>)}</tbody>
        </table></div>}
      </>}
    </details>
    <details className="evidence-inbox"><summary>Evidence review inbox</summary>
      <p>Source passages and model output are evidence to inspect, not proof that an event occurred. Decisions stay in this queue; they do not publish map incidents.</p>
      {!canReview ? <p className="automation-notice">Sign in as an incident moderator or administrator to access evidence reviews. Guest and driver accounts cannot approve them.</p>
        : <><button type="button" disabled={!!busy} onClick={() => void loadInbox()}>{busy === "inbox" ? "Loading evidence…" : items ? "Refresh pending evidence" : "Load pending evidence"}</button>
          {error && <p role="alert" className="automation-error">{error}</p>}
          {notice && <p role="status" className="automation-notice">{notice}</p>}
          {items?.length === 0 && <p>No evidence is waiting for review.</p>}
          {items?.map((item) => <article className="evidence-entry" key={item.id}>
            <p className="evidence-provenance">{item.source === "demo" ? "Synthetic demonstration" : "Submitted evidence · not verified"} · {timestampLabel(item.created_at)}</p>
            <h4>{item.claim}</h4>
            <ol>{item.evidence.map((passage, index) => {
              const url = evidenceSourceUrl(passage.source_url);
              return <li key={index}><p>{passage.text}</p><div className="evidence-source">{url ? <a href={url} target="_blank" rel="noopener noreferrer">Open source {index + 1}</a> : <span>No source link supplied</span>}<span>Observed: {timestampLabel(passage.observed_at)}</span></div></li>;
            })}</ol>
            {item.analysis && <details><summary>Model comparison output · not a truth verdict</summary><pre>{JSON.stringify(item.analysis, null, 2)}</pre></details>}
            <label className="review-note">Review note<textarea value={notes[item.id] ?? ""} minLength={3} maxLength={2000} rows={3}
              onChange={(event) => setNotes((previous) => ({ ...previous, [item.id]: event.target.value }))} placeholder="Explain your decision and any unresolved source or timing issues." /></label>
            <div className="review-actions"><button type="button" disabled={!!busy || (notes[item.id]?.trim().length ?? 0) < 3} onClick={() => void decide(item, "approved")}>Approve evidence review</button>
              <button type="button" disabled={!!busy || (notes[item.id]?.trim().length ?? 0) < 3} onClick={() => void decide(item, "rejected")}>Reject evidence review</button>
              {busy === item.id && <span role="status">Saving review…</span>}</div>
          </article>)}</>}
    </details>
    <TrafficFrameCheck client={client} session={session} />
    {!deployment.githubPages && <nav className="monitor-service-links" aria-label="Local monitoring services"><span>Local service consoles · availability not checked</span>
      <a href="http://localhost:5678" target="_blank" rel="noopener noreferrer">n8n ↗</a><a href="http://localhost:8082" target="_blank" rel="noopener noreferrer">Traccar ↗</a><a href="http://localhost:8080" target="_blank" rel="noopener noreferrer">ThingsBoard ↗</a>
    </nav>}
  </section>;
}
