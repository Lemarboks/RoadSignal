import type { Incident } from "@roadsignal/types";
import { useState } from "react";
import type { RoadSignalApiClient } from "../../lib/api-client";
import type { AssistantStatus, IncidentReport } from "../../lib/assistant";
import type { ResolvedPlace } from "../../lib/open-routing";
import { IncidentComposer } from "./incident-composer";

export function IncidentsPage({
  incidents,
  onReport,
  onModerate,
  client,
  signedIn,
  serviceEnabled,
  assistantStatus,
  initialPlace,
}: {
  incidents: Incident[];
  onReport: (report: IncidentReport) => Promise<void>;
  onModerate: (id: string, field: "confirmations" | "disputes") => void;
  client: RoadSignalApiClient;
  signedIn: boolean;
  serviceEnabled: boolean;
  assistantStatus: AssistantStatus | null;
  initialPlace: ResolvedPlace | null;
}) {
  const [composing, setComposing] = useState(false);
  const [query, setQuery] = useState("");
  const [type, setType] = useState("");
  const [confidence, setConfidence] = useState("");
  const [status, setStatus] = useState("active");
  const visible = incidents.filter((item) =>
    (!query || `${item.incidentType} ${item.description}`.toLowerCase().includes(query.toLowerCase())) &&
    (!type || item.incidentType === type) && (!confidence || item.confidence >= 0.75) && (!status || item.status === status));
  return (
    <>
      <section className="heading">
        <div>
          <p className="eyebrow">Community intelligence</p>
          <h1>Incidents</h1>
          <p>Review, confirm, dispute, and resolve recent reports.</p>
        </div>
        <button type="button" className="primary" aria-expanded={composing} onClick={() => setComposing(true)}>
          Report incident
        </button>
      </section>
      {composing && <IncidentComposer client={client} signedIn={signedIn} serviceEnabled={serviceEnabled}
        status={assistantStatus} initialPlace={initialPlace} onReport={onReport} onClose={() => setComposing(false)} />}
      <div className="filters">
        <input aria-label="Search incidents" placeholder="Search incidents" value={query} onChange={(event) => setQuery(event.target.value)} />
        <select aria-label="Filter by incident type" value={type} onChange={(event) => setType(event.target.value)}>
          <option value="">All types</option>
          {[...new Set(incidents.map((item) => item.incidentType))].map((value) => <option key={value}>{value}</option>)}
        </select>
        <select aria-label="Filter by confidence" value={confidence} onChange={(event) => setConfidence(event.target.value)}>
          <option value="">All confidence</option>
          <option value="high">High confidence</option>
        </select>
        <select aria-label="Filter by status" value={status} onChange={(event) => setStatus(event.target.value)}>
          <option value="active">Active</option>
          <option value="expired">Expired</option>
          <option value="resolved">Resolved</option>
          <option value="">All statuses</option>
        </select>
      </div>
      <section className="panel table-wrap">
        <table>
          <thead>
            <tr>
              <th>Incident</th>
              <th>Severity</th>
              <th>Reported</th>
              <th>Source</th>
              <th>Confidence</th>
              <th>Verification</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            {visible.map((incident) => (
              <tr key={incident.id} id={`incident-${encodeURIComponent(incident.id)}`} tabIndex={-1}>
                <td data-label="Incident">
                  <strong>{incident.incidentType}</strong>
                  <small>{incident.description}</small>
                </td>
                <td data-label="Severity">
                  <span className={`severity s${incident.severity}`}>
                    {incident.severity}
                  </span>
                </td>
                <td data-label="Reported">
                  {new Date(incident.occurredAt).toLocaleTimeString()}
                </td>
                <td data-label="Source">{incident.sourceType}</td>
                <td data-label="Confidence">
                  {Math.round(incident.confidence * 100)}%
                </td>
                <td data-label="Verification">
                  {incident.verificationStatus}
                  <small>
                    {incident.confirmations} confirms - {incident.disputes}{" "}
                    disputes
                  </small>
                </td>
                <td data-label="Actions">
                  <button
                    type="button"
                    onClick={() => onModerate(incident.id, "confirmations")}
                  >
                    Confirm
                  </button>
                  <button
                    type="button"
                    onClick={() => onModerate(incident.id, "disputes")}
                  >
                    Dispute
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {!visible.length && <p className="assistant-caption">No incidents match these filters.</p>}
      </section>
    </>
  );
}
