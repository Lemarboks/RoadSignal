"use client";
import { useEffect, useMemo, useState } from "react";
import type { Incident, RouteOption } from "@saferoute/types";
import { RouteMap as MapView } from "../components/route-map";

const API =
  process.env.NEXT_PUBLIC_API_URL ??
  (process.env.NODE_ENV === "development" ? "http://localhost:8000" : "");
const nav = [
  "Dashboard",
  "Route Planner",
  "Live Trips",
  "Incidents",
  "Risk Map",
  "Analytics",
  "Fleet",
  "Settings",
] as const;
type Page = (typeof nav)[number];
const fallbackRoutes: RouteOption[] = [
  {
    id: "route-balanced",
    name: "Balanced Route",
    durationMinutes: 29,
    distanceKm: 18.7,
    safetyScore: 87,
    confidence: 0.84,
    riskLevel: "low",
    recommended: true,
    differenceFromFastest: 5,
    factors: ["Traffic", "Road condition"],
    breakdown: {
      crime: 5,
      accident: 3,
      traffic: 6,
      weather: 1,
      roadCondition: 2,
      community: 1,
    },
    explanation:
      "Five minutes longer, avoiding the recent collision and elevated vehicle-crime corridor.",
    geometry: [
      { latitude: -33.925, longitude: 18.424 },
      { latitude: -33.936, longitude: 18.443 },
      { latitude: -33.951, longitude: 18.473 },
      { latitude: -33.981, longitude: 18.531 },
    ],
  },
  {
    id: "route-safest",
    name: "Safest Route",
    durationMinutes: 33,
    distanceKm: 20.4,
    safetyScore: 92,
    confidence: 0.81,
    riskLevel: "low",
    recommended: false,
    differenceFromFastest: 9,
    factors: ["Traffic", "Weather"],
    breakdown: {
      crime: 3,
      accident: 2,
      traffic: 4,
      weather: 1,
      roadCondition: 1,
      community: 1,
    },
    explanation: "Lowest known exposure, with nine additional travel minutes.",
    geometry: [
      { latitude: -33.925, longitude: 18.424 },
      { latitude: -33.918, longitude: 18.455 },
      { latitude: -33.931, longitude: 18.489 },
      { latitude: -33.981, longitude: 18.531 },
    ],
  },
  {
    id: "route-fastest",
    name: "Fastest Route",
    durationMinutes: 24,
    distanceKm: 17.1,
    safetyScore: 63,
    confidence: 0.88,
    riskLevel: "medium",
    recommended: false,
    differenceFromFastest: 0,
    factors: ["Crime", "Accident"],
    breakdown: {
      crime: 14,
      accident: 11,
      traffic: 8,
      weather: 1,
      roadCondition: 4,
      community: 3,
    },
    explanation:
      "Fastest arrival, but passes recent collision and vehicle-crime reports.",
    geometry: [
      { latitude: -33.925, longitude: 18.424 },
      { latitude: -33.941, longitude: 18.452 },
      { latitude: -33.963, longitude: 18.478 },
      { latitude: -33.981, longitude: 18.531 },
    ],
  },
];
const initialIncidents: Incident[] = [
  {
    id: "demo-1",
    incidentType: "Accident",
    severity: 4,
    sourceType: "Traffic provider",
    verificationStatus: "confirmed",
    confidence: 0.86,
    description: "Collision near Hospital Bend",
    occurredAt: new Date(Date.now() - 2100000).toISOString(),
    expiresAt: null,
    location: { latitude: -33.941, longitude: 18.452 },
    confirmations: 4,
    disputes: 0,
    status: "active",
  },
];
const riskClass = (score: number) =>
  score >= 80 ? "low" : score >= 60 ? "medium" : "high";

function SchematicMapView({
  routes,
  selected,
  progress = 0,
}: {
  routes: RouteOption[];
  selected: string;
  progress?: number;
}) {
  const colors: Record<string, string> = {
    "route-balanced": "#1976d2",
    "route-safest": "#1f9d61",
    "route-fastest": "#d45545",
  };
  const points = (r: RouteOption) =>
    r.geometry
      .map(
        (_, i) =>
          `${60 + i * 140},${235 - (i % 2) * 65 - (r.id === "route-safest" ? 35 : 0) + (r.id === "route-fastest" ? 28 : 0)}`,
      )
      .join(" ");
  return (
    <div className="map" aria-label="Interactive route risk map">
      <div className="map-label">Cape Town · Demonstration map</div>
      <svg viewBox="0 0 520 300" role="img">
        <path d="M0 65 Q95 92 135 42 T280 70 T520 38V300H0Z" fill="#dceaf3" />
        <g stroke="#c7ced4" strokeWidth="6" fill="none">
          <path d="M20 260L500 48" />
          <path d="M40 75L470 270" />
          <path d="M110 10L300 300" />
        </g>
        {routes.map((r) => (
          <polyline
            key={r.id}
            points={points(r)}
            fill="none"
            stroke={colors[r.id]}
            strokeWidth={selected === r.id ? 9 : 4}
            opacity={selected === r.id ? 1 : 0.35}
            strokeLinecap="round"
            strokeDasharray={r.id === "route-fastest" ? "10 7" : "0"}
          />
        ))}
        <circle
          cx={60 + (Math.min(progress, 100) / 100) * 420}
          cy={
            selected === "route-safest"
              ? 165
              : selected === "route-fastest"
                ? 263
                : 235
          }
          r="10"
          fill="#1769aa"
          stroke="white"
          strokeWidth="4"
        />
      </svg>
      <div className="legend">
        <span>
          <i className="dot green" />
          Low risk
        </span>
        <span>
          <i className="dot amber" />
          Medium
        </span>
        <span>
          <i className="dot red" />
          High
        </span>
      </div>
    </div>
  );
}
function Metric({
  label,
  value,
  tone = "",
}: {
  label: string;
  value: string | number;
  tone?: string;
}) {
  return (
    <div className="metric">
      <span>{label}</span>
      <strong className={tone}>{value}</strong>
    </div>
  );
}

export default function App() {
  const [page, setPage] = useState<Page>("Dashboard"),
    [routes, setRoutes] = useState(fallbackRoutes),
    [selected, setSelected] = useState("route-balanced"),
    [loading, setLoading] = useState(false),
    [notice, setNotice] = useState("");
  const [trip, setTrip] = useState<{
    active: boolean;
    paused: boolean;
    progress: number;
    score: number;
    alerts: string[];
  }>({ active: false, paused: false, progress: 0, score: 87, alerts: [] });
  const [incidents, setIncidents] = useState(initialIncidents),
    [origin, setOrigin] = useState("Cape Town CBD"),
    [destination, setDestination] = useState("Cape Town International Airport"),
    [audit, setAudit] = useState<string[]>([]);
  const route = routes.find((r) => r.id === selected) ?? routes[0];
  useEffect(() => {
    if (!trip.active || trip.paused) return;
    const timer = setInterval(
      () => setTrip((t) => ({ ...t, progress: Math.min(100, t.progress + 2) })),
      1000,
    );
    return () => clearInterval(timer);
  }, [trip.active, trip.paused]);
  async function findRoutes() {
    setLoading(true);
    setNotice("");
    try {
      const res = await fetch(`${API}/api/v1/routes/analyse`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          origin,
          destination,
          preference: "balanced",
          departure_time: new Date().toISOString(),
          vehicle_type: "car",
        }),
      });
      if (!res.ok) throw new Error();
      const data = await res.json();
      setRoutes(
        data.routes.map((r: any) => ({
          id: r.id,
          name: r.name,
          durationMinutes: r.duration_minutes,
          distanceKm: r.distance_km,
          safetyScore: r.safety_score,
          confidence: r.confidence,
          riskLevel: r.risk_level,
          recommended: r.recommended,
          differenceFromFastest: r.difference_from_fastest,
          factors: r.factors,
          breakdown: {
            crime: r.breakdown.crime,
            accident: r.breakdown.accident,
            traffic: r.breakdown.traffic,
            weather: r.breakdown.weather,
            roadCondition: r.breakdown.road_condition,
            community: r.breakdown.community,
          },
          explanation: r.explanation,
          geometry: r.geometry,
        })),
      );
      setNotice("Three routes analysed using current demonstration incidents.");
    } catch {
      setRoutes(fallbackRoutes);
      setNotice(
        "API unavailable — showing deterministic offline demonstration data.",
      );
    } finally {
      setLoading(false);
    }
  }
  function startTrip() {
    setTrip({
      active: true,
      paused: false,
      progress: 2,
      score: route.safetyScore,
      alerts: [],
    });
    setPage("Live Trips");
    setAudit((a) => ["Trip started on Balanced Route", ...a]);
  }
  function inject(type = "Accident") {
    const item: Incident = {
      id: `local-${Date.now()}`,
      incidentType: type,
      severity: 5,
      sourceType: "Development simulator",
      verificationStatus: "unverified",
      confidence: 0.25,
      description: `High-severity ${type.toLowerCase()} reported on the active route`,
      occurredAt: new Date().toISOString(),
      expiresAt: null,
      location: { latitude: -33.951, longitude: 18.473 },
      confirmations: 0,
      disputes: 0,
      status: "active",
    };
    setIncidents((x) => [item, ...x]);
    setTrip((t) => ({
      ...t,
      score: Math.max(35, t.score - 19),
      alerts: [
        `${type} ahead. Safer Route is 4 minutes longer. Reroute recommended.`,
        ...t.alerts,
      ],
    }));
    setAudit((a) => [
      `${type} injected; route score recalculated; fleet alerted`,
      ...a,
    ]);
    setNotice("Fleet alert published and safer reroute calculated.");
  }
  function moderate(id: string, kind: "confirmations" | "disputes") {
    setIncidents((items) =>
      items.map((i) =>
        i.id === id
          ? {
              ...i,
              [kind]: i[kind] + 1,
              confidence: Math.min(
                0.95,
                Math.max(
                  0.1,
                  i.confidence + (kind === "confirmations" ? 0.15 : -0.12),
                ),
              ),
              verificationStatus:
                kind === "confirmations"
                  ? "community-confirmed"
                  : i.verificationStatus,
            }
          : i,
      ),
    );
    setAudit((a) => [
      `Incident ${kind === "confirmations" ? "confirmed" : "disputed"}; confidence updated`,
      ...a,
    ]);
  }
  const dashboard = (
    <>
      <section className="heading">
        <div>
          <p className="eyebrow">Friday, 17 July · Cape Town</p>
          <h1>Fleet operations overview</h1>
          <p>
            Real-time route-risk intelligence across demonstration operations.
          </p>
        </div>
        <button className="primary" onClick={() => setPage("Route Planner")}>
          Plan a safe route
        </button>
      </section>
      <div className="metrics">
        <Metric label="Active drivers" value="3 / 10" />
        <Metric label="Fleet safety score" value="84.2" tone="good" />
        <Metric
          label="Active incidents"
          value={incidents.filter((i) => i.status === "active").length}
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
            trip.alerts.map((x) => (
              <div className="alert danger-bg" key={x}>
                ⚠ {x}
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
          ].map(([n, s]) => (
            <div className="bar" key={n}>
              <span>{n}</span>
              <i>
                <b style={{ width: `${s}%` }} />
              </i>
              <strong>{s}</strong>
            </div>
          ))}
        </section>
      </div>
    </>
  );
  const planner = (
    <>
      <section className="heading">
        <div>
          <p className="eyebrow">Route intelligence</p>
          <h1>Route Planner</h1>
          <p>Compare travel time against confidence-weighted route risk.</p>
        </div>
      </section>
      <div className="planner">
        <section className="panel controls">
          <label>
            Origin
            <input value={origin} onChange={(e) => setOrigin(e.target.value)} />
          </label>
          <label>
            Destination
            <input
              value={destination}
              onChange={(e) => setDestination(e.target.value)}
            />
          </label>
          <div className="row">
            <label>
              Departure
              <input type="datetime-local" defaultValue="2026-07-17T14:30" />
            </label>
            <label>
              Vehicle
              <select>
                <option>Car</option>
                <option>Motorcycle</option>
                <option>Van</option>
              </select>
            </label>
          </div>
          <label>
            Preference
            <select>
              <option>Balanced</option>
              <option>Safest</option>
              <option>Fastest</option>
            </select>
          </label>
          <button
            className="primary wide"
            onClick={findRoutes}
            disabled={loading}
          >
            {loading ? "Analysing risk…" : "Find routes"}
          </button>
        </section>
        <MapView routes={routes} selected={selected} />
      </div>
      <div className="route-grid">
        {routes.map((r) => (
          <button
            className={`route-card ${selected === r.id ? "selected" : ""}`}
            onClick={() => setSelected(r.id)}
            key={r.id}
          >
            {r.recommended && <em>Recommended</em>}
            <h3>{r.name}</h3>
            <div className="route-stats">
              <strong>{r.durationMinutes} min</strong>
              <span>{r.distanceKm} km</span>
            </div>
            <div className={`score ${riskClass(r.safetyScore)}`}>
              {r.safetyScore}
              <small>/100 safety</small>
            </div>
            <p>
              {r.differenceFromFastest
                ? `${r.differenceFromFastest} minutes slower than fastest`
                : "Fastest arrival"}
            </p>
            <div className="chips">
              {r.factors.map((f) => (
                <span key={f}>{f}</span>
              ))}
            </div>
          </button>
        ))}
      </div>
      <section className="panel explanation">
        <h2>Why this route?</h2>
        <div className="risk-cols">
          <div>
            <div className={`big-score ${riskClass(route.safetyScore)}`}>
              {route.safetyScore}
            </div>
            <span>Overall safety estimate</span>
          </div>
          {Object.entries(route.breakdown).map(([k, v]) => (
            <Metric
              key={k}
              label={k.replace(/([A-Z])/g, " $1")}
              value={`${Math.round(100 - Number(v))}/100`}
            />
          ))}
        </div>
        <p>{route.explanation}</p>
        <p className="disclaimer">
          Safety scores are decision-support estimates based on available data.
          They do not measure or guarantee personal safety.
        </p>
        <button className="primary" onClick={startTrip}>
          Start simulated trip
        </button>
      </section>
    </>
  );
  const live = (
    <>
      <section className="heading">
        <div>
          <p className="eyebrow">
            {trip.active ? "Trip in progress" : "No active trip"}
          </p>
          <h1>Live Trip</h1>
          <p>Cape Town CBD → Cape Town International Airport</p>
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
          <div className="progress">
            <i style={{ width: `${trip.progress}%` }} />
          </div>
          {trip.alerts.map((x) => (
            <div className="alert danger-bg" key={x}>
              <strong>Reroute recommended</strong>
              <br />
              {x}
              <button
                onClick={() => {
                  setSelected("route-safest");
                  setTrip((t) => ({ ...t, score: 92, alerts: [] }));
                  setAudit((a) => ["Safer reroute accepted", ...a]);
                }}
              >
                Accept safer route
              </button>
            </div>
          ))}
          <div className="actions">
            <button
              onClick={() => setTrip((t) => ({ ...t, paused: !t.paused }))}
            >
              {trip.paused ? "Resume" : "Pause"}
            </button>
            <button onClick={() => inject("Accident")}>
              Simulate accident
            </button>
            <button onClick={() => inject("Crime report")}>
              Simulate crime
            </button>
            <button
              className="danger-btn"
              onClick={() => {
                setTrip((t) => ({
                  ...t,
                  active: false,
                  paused: true,
                  progress: 100,
                }));
                setAudit((a) => ["Trip completed and history stored", ...a]);
              }}
            >
              End trip
            </button>
          </div>
          <p className="dev">
            Development simulator · events are demonstration data
          </p>
        </section>
      </div>
      <section className="panel">
        <h2>Trip audit history</h2>
        {audit.length ? (
          audit.map((x, i) => (
            <div className="timeline" key={i}>
              <i />
              {x}
            </div>
          ))
        ) : (
          <div className="empty">Start a trip to create audit events.</div>
        )}
      </section>
    </>
  );
  const incidentPage = (
    <>
      <section className="heading">
        <div>
          <p className="eyebrow">Community intelligence</p>
          <h1>Incidents</h1>
          <p>Review, confirm, dispute, and resolve recent reports.</p>
        </div>
        <button className="primary" onClick={() => inject("Road closure")}>
          Report incident
        </button>
      </section>
      <div className="filters">
        <input placeholder="Search incidents" />
        <select>
          <option>All types</option>
          <option>Accident</option>
          <option>Crime</option>
        </select>
        <select>
          <option>All confidence</option>
          <option>High confidence</option>
        </select>
        <select>
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
            {incidents.map((i) => (
              <tr key={i.id}>
                <td>
                  <strong>{i.incidentType}</strong>
                  <small>{i.description}</small>
                </td>
                <td>
                  <span className={`severity s${i.severity}`}>
                    {i.severity}
                  </span>
                </td>
                <td>{new Date(i.occurredAt).toLocaleTimeString()}</td>
                <td>{i.sourceType}</td>
                <td>{Math.round(i.confidence * 100)}%</td>
                <td>
                  {i.verificationStatus}
                  <small>
                    {i.confirmations} confirms · {i.disputes} disputes
                  </small>
                </td>
                <td>
                  <button onClick={() => moderate(i.id, "confirmations")}>
                    Confirm
                  </button>
                  <button onClick={() => moderate(i.id, "disputes")}>
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
  const analyticsPage = (
    <>
      <section className="heading">
        <div>
          <p className="eyebrow">Last 30 days · Demonstration data</p>
          <h1>{page}</h1>
          <p>Operational safety performance and confidence-weighted trends.</p>
        </div>
      </section>
      <div className="metrics">
        <Metric label="Average safety" value="84.2" />
        <Metric label="Reroutes triggered" value="38" />
        <Metric label="Recommendations accepted" value="74%" />
        <Metric label="Alert response" value="2m 18s" />
      </div>
      <div className="grid two">
        <section className="panel">
          <h2>Safety score by hour</h2>
          <div className="chart">
            {[78, 81, 84, 86, 83, 79, 74, 69, 73, 80, 85, 88].map((v, i) => (
              <i key={i} style={{ height: `${v}%` }} title={`${v}`} />
            ))}
          </div>
        </section>
        <section className="panel">
          <h2>Incident categories</h2>
          {[
            ["Traffic accidents", 34],
            ["Crime reports", 26],
            ["Road conditions", 21],
            ["Disruptions", 12],
            ["Weather", 7],
          ].map(([n, v]) => (
            <div className="bar" key={n}>
              <span>{n}</span>
              <i>
                <b style={{ width: `${Number(v) * 2}%` }} />
              </i>
              <strong>{v}%</strong>
            </div>
          ))}
        </section>
      </div>
    </>
  );
  return (
    <div className="shell">
      <aside>
        <div className="brand">
          <b>SR</b>
          <span>
            SafeRoute <strong>AI</strong>
            <small>Route-risk intelligence</small>
          </span>
        </div>
        <nav>
          {nav.map((n) => (
            <button
              className={page === n ? "active" : ""}
              onClick={() => setPage(n)}
              key={n}
            >
              <i>{["▦", "⌁", "●", "△", "◎", "▥", "♙", "⚙"][nav.indexOf(n)]}</i>
              {n}
              {n === "Incidents" && <em>{incidents.length}</em>}
            </button>
          ))}
        </nav>
        <div className="user">
          <span>AM</span>
          <div>
            <strong>Alex Morgan</strong>
            <small>Fleet manager</small>
          </div>
        </div>
      </aside>
      <main>
        {notice && (
          <div className="toast" onClick={() => setNotice("")}>
            {notice} ×
          </div>
        )}
        {page === "Dashboard"
          ? dashboard
          : page === "Route Planner"
            ? planner
            : page === "Live Trips"
              ? live
              : page === "Incidents"
                ? incidentPage
                : analyticsPage}
      </main>
    </div>
  );
}
