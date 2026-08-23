import { demoDrivers } from "../demo-data";
import type { AppPage } from "./operations-pages";

const riskClass = (score: number) => score >= 80 ? "low" : score >= 60 ? "medium" : "high";
type Navigate = (page: AppPage) => void;

export function FleetPage({
  query,
  status,
  visibleDrivers,
  onQueryChange,
  onStatusChange,
  onNavigate,
  onViewTrip,
}: {
  query: string;
  status: string;
  visibleDrivers: Array<(typeof demoDrivers)[number]>;
  onQueryChange: (query: string) => void;
  onStatusChange: (status: string) => void;
  onNavigate: Navigate;
  onViewTrip: (driverName: string) => void;
}) {
  return (
    <>
      <section className="heading fleet-heading">
        <div>
          <p className="eyebrow">Driver operations · Demonstration data</p>
          <h1>Fleet roster</h1>
          <p>
            Find drivers, inspect trip status, and move directly to active
            operations.
          </p>
        </div>
        <button
          type="button"
          className="primary"
          onClick={() => onNavigate("Live Trips")}
        >
          Monitor live trips
        </button>
      </section>
      <div className="fleet-summary" aria-label="Fleet status summary">
        <div>
          <span>Active</span>
          <strong>3</strong>
        </div>
        <div>
          <span>On trip</span>
          <strong>2</strong>
        </div>
        <div>
          <span>Attention</span>
          <strong className="danger">1</strong>
        </div>
        <div>
          <span>Offline</span>
          <strong>1</strong>
        </div>
      </div>
      <div className="fleet-controls">
        <label>
          <span className="sr-only">Search fleet</span>
          <input
            value={query}
            onChange={(event) => onQueryChange(event.target.value)}
            placeholder="Search driver, vehicle or route"
          />
        </label>
        <label>
          <span className="sr-only">Filter fleet status</span>
          <select
            value={status}
            onChange={(event) => onStatusChange(event.target.value)}
          >
            <option>All statuses</option>
            <option>On trip</option>
            <option>Attention</option>
            <option>Available</option>
            <option>Offline</option>
          </select>
        </label>
        <span aria-live="polite">{visibleDrivers.length} drivers shown</span>
      </div>
      <section className="fleet-table-wrap" aria-labelledby="fleet-table-title">
        <div className="section-heading-row">
          <div>
            <h2 id="fleet-table-title">Drivers and vehicles</h2>
            <p>Operational status and latest known update</p>
          </div>
        </div>
        {visibleDrivers.length ? (
          <table className="fleet-table">
            <thead>
              <tr>
                <th>Driver</th>
                <th>Status</th>
                <th>Current assignment</th>
                <th>Safety estimate</th>
                <th>Updated</th>
                <th>Action</th>
              </tr>
            </thead>
            <tbody>
              {visibleDrivers.map((driver) => (
                <tr key={driver.vehicle}>
                  <td data-label="Driver">
                    <strong>{driver.name}</strong>
                    <small>{driver.vehicle}</small>
                  </td>
                  <td data-label="Status">
                    <span
                      className={`driver-status ${driver.status.toLowerCase().replace(" ", "-")}`}
                    >
                      {driver.status}
                    </span>
                  </td>
                  <td data-label="Current assignment">{driver.route}</td>
                  <td data-label="Safety estimate">
                    <strong className={riskClass(driver.score)}>
                      {driver.score}/100
                    </strong>
                  </td>
                  <td data-label="Updated">{driver.updated}</td>
                  <td data-label="Action">
                    <button
                      type="button"
                      onClick={() => onViewTrip(driver.name)}
                    >
                      View trip
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : (
          <div className="empty fleet-empty">
            No drivers match this search. Clear the search or choose another
            status.
          </div>
        )}
      </section>
    </>
  );
}
