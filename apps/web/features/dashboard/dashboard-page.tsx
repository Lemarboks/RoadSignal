import type { Incident, RouteOption } from "@roadsignal/types";
import { Metric } from "../../components/metric";
import { RouteMap as MapView } from "../../components/route-map";

export function DashboardPage({
  incidents,
  routes,
  selected,
  trip,
  onPlanRoute,
}: {
  incidents: Incident[];
  routes: RouteOption[];
  selected: string;
  trip: { progress: number; score: number; alerts: string[] };
  onPlanRoute: () => void;
}) {
  return (
    <>
      <section className="heading">
        <div>
          <p className="eyebrow">Friday, 17 July - Cape Town</p>
          <h1>Fleet operations overview</h1>
          <p>
            Real-time route-risk intelligence across demonstration operations.
          </p>
        </div>
        <button type="button" className="primary" onClick={onPlanRoute}>
          Plan a safe route
        </button>
      </section>
      <div className="metrics">
        <Metric label="Active drivers" value="3 / 10" />
        <Metric label="Fleet safety score" value="84.2" tone="good" />
        <Metric
          label="Active incidents"
          value={
            incidents.filter((incident) => incident.status === "active").length
          }
        />
        <Metric
          label="High-risk drivers"
          value={trip.score < 60 ? 1 : 0}
          tone={trip.score < 60 ? "danger" : "good"}
        />
        <Metric label="Trips today" value="20" />
      </div>
      <div className="grid two">
        <section className="panel">
          <h2>Live fleet map</h2>
          <MapView
            routes={routes}
            selected={selected}
            progress={trip.progress}
          />
        </section>
        <section className="panel">
          <h2>Recent alert feed</h2>
          {trip.alerts.length ? (
            trip.alerts.map((alert) => (
              <div className="alert danger-bg" key={alert}>
                Warning: {alert}
              </div>
            ))
          ) : (
            <div className="empty">
              No emergency fleet alerts. Monitoring 3 active trips.
            </div>
          )}
          <h3>Risk by area</h3>
          {[
            ["Cape Town CBD", 82],
            ["Woodstock", 71],
            ["Pinelands", 88],
            ["Athlone", 64],
          ].map(([name, score]) => (
            <div className="bar" key={name}>
              <span>{name}</span>
              <i>
                <b style={{ width: `${score}%` }} />
              </i>
              <strong>{score}</strong>
            </div>
          ))}
        </section>
      </div>
    </>
  );
}
