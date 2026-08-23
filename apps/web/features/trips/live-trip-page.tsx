import type { RouteOption } from "@roadsignal/types";
import { Metric } from "../../components/metric";
import { RouteMap as MapView } from "../../components/route-map";

const riskClass = (score: number) =>
  score >= 80 ? "low" : score >= 60 ? "medium" : "high";

export function LiveTripPage({
  trip,
  routes,
  selected,
  origin,
  destination,
  audit,
  safestAlternative,
  onAcceptSaferRoute,
  onTogglePause,
  onSimulateIncident,
  onEndTrip,
}: {
  trip: {
    active: boolean;
    paused: boolean;
    progress: number;
    score: number;
    alerts: string[];
  };
  routes: RouteOption[];
  selected: string;
  origin: string;
  destination: string;
  audit: string[];
  safestAlternative?: RouteOption;
  onAcceptSaferRoute: (route: RouteOption) => void;
  onTogglePause: () => void;
  onSimulateIncident: (type: string) => void;
  onEndTrip: () => void;
}) {
  return (
    <>
      <section className="heading">
        <div>
          <p className="eyebrow">
            {trip.active ? "Trip in progress" : "No active trip"}
          </p>
          <h1>Live Trip</h1>
          <p>
            {origin} to {destination}
          </p>
        </div>
        <div className={`pill ${riskClass(trip.score)}`}>
          {trip.score}/100 safety
        </div>
      </section>
      <div className="grid live">
        <MapView routes={routes} selected={selected} progress={trip.progress} />
        <section className="panel">
          <Metric
            label="ETA"
            value={`${Math.max(1, Math.round(29 * (1 - trip.progress / 100)))} min`}
          />
          <Metric label="Progress" value={`${trip.progress}%`} />
          <Metric
            label="Upcoming risk"
            value={trip.alerts.length ? "High" : "Low"}
            tone={trip.alerts.length ? "danger" : "good"}
          />
          <div
            className="progress"
            role="progressbar"
            aria-label="Simulated trip progress"
            aria-valuemin={0}
            aria-valuemax={100}
            aria-valuenow={trip.progress}
          >
            <i style={{ width: `${trip.progress}%` }} />
          </div>
          {trip.alerts.map((alert) => (
            <div className="alert danger-bg" key={alert}>
              <strong>Reroute recommended</strong>
              <br />
              {alert}
              {safestAlternative && (
                <button
                  type="button"
                  onClick={() => onAcceptSaferRoute(safestAlternative)}
                >
                  Accept safer route
                </button>
              )}
            </div>
          ))}
          <div className="actions">
            <button type="button" onClick={onTogglePause}>
              {trip.paused ? "Resume" : "Pause"}
            </button>
            <button
              type="button"
              onClick={() => onSimulateIncident("Accident")}
            >
              Simulate accident
            </button>
            <button
              type="button"
              onClick={() => onSimulateIncident("Crime report")}
            >
              Simulate crime
            </button>
            <button type="button" className="danger-btn" onClick={onEndTrip}>
              End trip
            </button>
          </div>
          <p className="dev">
            Development simulator - events are demonstration data
          </p>
        </section>
      </div>
      <section className="panel">
        <h2>Trip audit history</h2>
        {audit.length ? (
          audit.map((entry, index) => (
            <div className="timeline" key={index}>
              <i />
              {entry}
            </div>
          ))
        ) : (
          <div className="empty">Start a trip to create audit events.</div>
        )}
      </section>
    </>
  );
}
