import type { Incident } from "@roadsignal/types";

export function IncidentsPage({
  incidents,
  onReport,
  onModerate,
}: {
  incidents: Incident[];
  onReport: () => void;
  onModerate: (id: string, field: "confirmations" | "disputes") => void;
}) {
  return (
    <>
      <section className="heading">
        <div>
          <p className="eyebrow">Community intelligence</p>
          <h1>Incidents</h1>
          <p>Review, confirm, dispute, and resolve recent reports.</p>
        </div>
        <button type="button" className="primary" onClick={onReport}>
          Report incident
        </button>
      </section>
      <div className="filters">
        <input aria-label="Search incidents" placeholder="Search incidents" />
        <select aria-label="Filter by incident type">
          <option>All types</option>
          <option>Accident</option>
          <option>Crime</option>
        </select>
        <select aria-label="Filter by confidence">
          <option>All confidence</option>
          <option>High confidence</option>
        </select>
        <select aria-label="Filter by status">
          <option>Active</option>
          <option>Expired</option>
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
            {incidents.map((incident) => (
              <tr key={incident.id}>
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
      </section>
    </>
  );
}
