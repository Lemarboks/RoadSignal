import { Metric } from "../../components/metric";
import type { FleetAnalytics } from "../demo-data";

export function AnalyticsPage({
  analytics,
  source,
  window,
  onWindowChange,
  onOpenFleetQueue,
}: {
  analytics: FleetAnalytics;
  source: "demo" | "api";
  window: "7" | "30" | "90";
  onWindowChange: (window: "7" | "30" | "90") => void;
  onOpenFleetQueue: () => void;
}) {
  const scores =
    window === "7"
      ? [74, 79, 76, 82, 84, 83, 88]
      : window === "90"
        ? [68, 72, 70, 76, 74, 79, 81, 78, 84, 82, 86, 88]
        : [78, 81, 84, 86, 83, 79, 74, 69, 73, 80, 85, 88];
  return (
    <>
      <section className="heading">
        <div>
          <p className="eyebrow">Operational trends · Demonstration data</p>
          <h1>Performance analytics</h1>
          <p>Operational safety performance and confidence-weighted trends.</p>
        </div>
        <div className="analytics-actions">
          <div className="segmented-control" aria-label="Analytics time range">
            {(["7", "30", "90"] as const).map((days) => (
              <button
                type="button"
                key={days}
                aria-pressed={window === days}
                onClick={() => onWindowChange(days)}
              >
                {days} days
              </button>
            ))}
          </div>
          <span className={`evidence-source ${source}`}>
            {source === "api" ? "Live from API" : "Demo data"}
          </span>
        </div>
      </section>
      <div className="analytics-summary">
        <Metric
          label="Average safety"
          value={analytics.average_safety_score.toFixed(1)}
        />
        <Metric label="Active incidents" value={analytics.active_incidents} />
        <Metric
          label="Trips completed today"
          value={analytics.trips_completed_today}
        />
        <Metric label="Recommendations accepted" value="74%" />
      </div>
      <div className="analytics-layout">
        <section className="analytics-trend">
          <div className="section-heading-row">
            <div>
              <h2>Safety estimate trend</h2>
              <p>Selected {window}-day demonstration window</p>
            </div>
            <strong>+4.8%</strong>
          </div>
          <div
            className="chart analytics-chart"
            role="img"
            aria-label="Safety estimates range from 69 to 88, ending at 88"
          >
            {scores.map((value, index) => (
              <i
                key={index}
                style={{ height: `${value}%` }}
                title={`${value}`}
              />
            ))}
          </div>
        </section>
        <section className="analytics-breakdown">
          <div className="section-heading-row">
            <div>
              <h2>Incident mix</h2>
              <p>Share of recorded signals</p>
            </div>
          </div>
          {[
            ["Traffic accidents", 34],
            ["Crime reports", 26],
            ["Road conditions", 21],
            ["Disruptions", 12],
            ["Weather", 7],
          ].map(([name, value]) => (
            <div className="bar" key={name}>
              <span>{name}</span>
              <i>
                <b style={{ width: `${Number(value) * 2}%` }} />
              </i>
              <strong>{value}%</strong>
            </div>
          ))}
          <div className="analytics-exception">
            <span>Needs attention</span>
            <strong>{analytics.high_risk_drivers} high-risk driver</strong>
            <button type="button" onClick={onOpenFleetQueue}>
              Open fleet queue
            </button>
          </div>
        </section>
      </div>
    </>
  );
}
