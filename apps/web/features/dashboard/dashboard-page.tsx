import type { Incident, RouteOption } from "@roadsignal/types";
import { Metric } from "../../components/metric";
import { RouteMap as MapView } from "../../components/route-map";
import type { RouteWeather } from "../../lib/open-weather";
import { demoDrivers } from "../demo-data";

export function DashboardPage({
  incidents,
  routes,
  selected,
  trip,
  weather,
  weatherStatus,
  onPlanRoute,
  onSelectRoute,
  onOpenFleet,
}: {
  incidents: Incident[];
  routes: RouteOption[];
  selected: string;
  trip: { progress: number; score: number; alerts: string[] };
  weather: RouteWeather | null;
  weatherStatus: "loading" | "ready" | "unavailable";
  onPlanRoute: () => void;
  onSelectRoute: (routeId: string) => void;
  onOpenFleet: () => void;
}) {
  const areaScores = [
    { name: "Cape Town CBD", score: 82 },
    { name: "Woodstock", score: 71 },
    { name: "Pinelands", score: 88 },
    { name: "Athlone", score: 64 },
  ];

  return (
    <div className="dashboard-page">
      <section className="heading dashboard-heading">
        <div>
          <p className="eyebrow dashboard-date">Cape Town · Fleet demonstration</p>
          <h1>Fleet operations overview</h1>
          <p>
            Real-time route-risk intelligence across demonstration operations.
          </p>
        </div>
        <button type="button" className="primary" onClick={onPlanRoute}>
          Plan a safe route
        </button>
      </section>
      <div className="metrics dashboard-metrics" aria-label="Fleet overview metrics">
        <Metric label="Drivers online" value={`${demoDrivers.filter((driver) => driver.status !== "Offline").length} / ${demoDrivers.length}`} />
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
      <div className="grid two dashboard-grid">
        <section className="panel dashboard-map-panel">
          <header className="dashboard-panel-heading">
            <div>
              <span>Network view</span>
              <h2>Route overview</h2>
            </div>
            <button type="button" className="dashboard-track-link" onClick={onOpenFleet}>Open fleet replay</button>
          </header>
          <MapView
            routes={routes}
            selected={selected}
            progress={trip.progress}
            weather={weather}
            weatherStatus={weatherStatus}
            incidents={incidents}
            onSelectRoute={onSelectRoute}
          />
        </section>
        <section className="panel dashboard-alert-feed">
          <header className="dashboard-panel-heading">
            <div>
              <span>Attention queue</span>
              <h2>Recent alert feed</h2>
            </div>
          </header>
          {trip.alerts.length ? (
            trip.alerts.map((alert) => (
              <div className="alert danger-bg" key={alert}>
                Warning: {alert}
              </div>
            ))
          ) : (
            <div className="empty">
              <strong>All clear</strong>
              <span>No alerts in the selected demonstration trip.</span>
            </div>
          )}
          <div className="dashboard-risk-heading">
            <span>Area status</span>
            <h3>Safety by area</h3>
          </div>
          {areaScores.map(({ name, score }) => (
            <div
              className={`bar ${score >= 80 ? "low-risk" : score >= 70 ? "medium-risk" : "high-risk"}`}
              key={name}
            >
              <span>{name}</span>
              <i>
                <b style={{ width: `${score}%` }} />
              </i>
              <strong>{score}</strong>
            </div>
          ))}
        </section>
      </div>
    </div>
  );
}
