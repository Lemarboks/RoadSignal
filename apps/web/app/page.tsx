"use client";
import { useEffect, useMemo, useState } from "react";
import type { Incident, RouteOption, RoutePreference } from "@roadsignal/types";
import { RouteMap as MapView } from "../components/route-map";
import { PlaceSearch } from "../components/place-search";
import { navIcons } from "../components/nav-icons";
import { demoRouteGeometry } from "../lib/demo-route-geometry";
import {
  analyseOpenRoutes,
  PlaceNotFoundError,
  type ResolvedPlace,
} from "../lib/open-routing";
import {
  applyWeatherRisk,
  fetchRouteWeather,
  type RouteWeather,
} from "../lib/open-weather";
import { connectRealtimeEvents } from "../lib/realtime-events";
import { AuthPanel } from "../components/auth-panel";
import { EntryGate } from "../components/entry-gate";
import { RoadSignalApiClient, type SessionSnapshot } from "../lib/api-client";
import { packagedRiskEvidence, type RiskEvidence } from "../lib/risk-evidence";

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
type DataMode = "demo" | "public" | "api";
type ApiRoute = {
  id: string;
  name: string;
  duration_minutes: number;
  distance_km: number;
  safety_score: number;
  confidence: number;
  risk_level: RouteOption["riskLevel"];
  recommended: boolean;
  difference_from_fastest: number;
  factors: string[];
  breakdown: { crime: number; accident: number; traffic: number; weather: number; road_condition: number; community: number };
  explanation: string;
  geometry: RouteOption["geometry"];
};
type FleetAnalytics = {
  active_drivers: number;
  high_risk_drivers: number;
  average_safety_score: number;
  active_incidents: number;
  trips_completed_today: number;
};
const demoFleetAnalytics: FleetAnalytics = {
  active_drivers: 3,
  high_risk_drivers: 1,
  average_safety_score: 84.2,
  active_incidents: 2,
  trips_completed_today: 20,
};
type WeatherStatus = "loading" | "ready" | "unavailable";
type RealtimeStatus = "offline" | "connecting" | "connected" | "disconnected" | "unauthorized";
type LocationPermissionStatus =
  | "checking"
  | "prompt"
  | "granted"
  | "denied"
  | "unsupported";
const fallbackRoutes: RouteOption[] = [
  {
    id: "route-balanced",
    name: "Balanced Route",
    durationMinutes: 28,
    distanceKm: 25.5,
    safetyScore: 87,
    confidence: 0.84,
    riskLevel: "low",
    recommended: true,
    differenceFromFastest: 8,
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
      "Eight minutes longer, following a distinct road corridor around recent demonstration incidents.",
    geometry: demoRouteGeometry["route-balanced"],
  },
  {
    id: "route-safest",
    name: "Safest Route",
    durationMinutes: 30,
    distanceKm: 24.6,
    safetyScore: 92,
    confidence: 0.81,
    riskLevel: "low",
    recommended: false,
    differenceFromFastest: 10,
    factors: ["Traffic", "Weather"],
    breakdown: {
      crime: 3,
      accident: 2,
      traffic: 4,
      weather: 1,
      roadCondition: 1,
      community: 1,
    },
    explanation: "Lowest known demonstration exposure, with ten additional travel minutes.",
    geometry: demoRouteGeometry["route-safest"],
  },
  {
    id: "route-fastest",
    name: "Fastest Route",
    durationMinutes: 20,
    distanceKm: 19.9,
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
    geometry: demoRouteGeometry["route-fastest"],
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
const defaultOrigin: ResolvedPlace = {
  displayName:
    "Cape Town City Centre, City of Cape Town, Western Cape, South Africa",
  latitude: -33.9249,
  longitude: 18.4241,
};
const defaultDestination: ResolvedPlace = {
  displayName:
    "Cape Town International Airport, City of Cape Town, Western Cape, South Africa",
  latitude: -33.9715,
  longitude: 18.6021,
};
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
      <div className="map-label">Cape Town - Demonstration map</div>
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
    [locating, setLocating] = useState(false),
    [locationPermission, setLocationPermission] =
      useState<LocationPermissionStatus>("checking"),
    [notice, setNotice] = useState(""),
    [dataMode, setDataMode] = useState<DataMode>("demo"),
    [weather, setWeather] = useState<RouteWeather | null>(null),
    [weatherStatus, setWeatherStatus] = useState<WeatherStatus>("loading"),
    [realtimeStatus, setRealtimeStatus] = useState<RealtimeStatus>(API ? "connecting" : "offline"),
    [backendStatus, setBackendStatus] = useState<"unknown" | "waking" | "ready" | "unavailable">(
      API ? "waking" : "unknown",
    );
  const apiClient = useMemo(() => new RoadSignalApiClient(API), []);
  const [session, setSession] = useState<SessionSnapshot | null>(null);
  const [entered, setEntered] = useState(false);
  const [riskEvidence, setRiskEvidence] = useState<RiskEvidence>(packagedRiskEvidence);
  const [riskEvidenceSource, setRiskEvidenceSource] = useState<"packaged" | "api">("packaged");
  const [fleetAnalytics, setFleetAnalytics] = useState<FleetAnalytics>(demoFleetAnalytics);
  const [fleetAnalyticsSource, setFleetAnalyticsSource] = useState<"demo" | "api">("demo");
  const [trip, setTrip] = useState<{
    id?: string;
    active: boolean;
    paused: boolean;
    progress: number;
    score: number;
    alerts: string[];
  }>({ active: false, paused: false, progress: 0, score: 87, alerts: [] });
  const [incidents, setIncidents] = useState(initialIncidents),
    [origin, setOrigin] = useState("Cape Town City Centre"),
    [destination, setDestination] = useState("Cape Town International Airport"),
    [preference, setPreference] = useState<RoutePreference>("balanced"),
    [resolvedOrigin, setResolvedOrigin] = useState<ResolvedPlace | null>(
      defaultOrigin,
    ),
    [resolvedDestination, setResolvedDestination] =
      useState<ResolvedPlace | null>(defaultDestination),
    [audit, setAudit] = useState<string[]>([]);
  const route = routes.find((r) => r.id === selected) ?? routes[0];
  const safestAlternative = routes
    .filter((candidate) => candidate.id !== selected)
    .sort((first, second) => second.safetyScore - first.safetyScore)[0];
  useEffect(() => {
    if (!API) return;
    return connectRealtimeEvents({
      apiUrl: API,
      accessToken: session?.accessToken,
      onStatus: setRealtimeStatus,
      onEvents: (events) => {
        setAudit((current) => [
          ...events.map((event) => `${event.type.replaceAll(".", " ")}: live API event received`),
          ...current,
        ].slice(0, 100));
        if (events.some((event) => event.type === "route.risk_changed")) {
          setNotice("Live route risk changed. Review the active trip and available alternatives.");
        }
      },
    });
  }, [session?.accessToken]);
  useEffect(() => {
    if (!API) return;
    let active = true;
    const controller = new AbortController();
    // Free-tier hosts (e.g. Render) can take up to ~60s to wake a sleeping
    // instance; a generous one-off health check lets the UI say so instead
    // of the first search silently timing out into the public-data fallback.
    const timeout = window.setTimeout(() => controller.abort(), 55_000);
    setBackendStatus("waking");
    fetch(`${API}/api/v1/health`, { signal: controller.signal })
      .then((response) => {
        if (active) setBackendStatus(response.ok ? "ready" : "unavailable");
      })
      .catch(() => {
        if (active) setBackendStatus("unavailable");
      })
      .finally(() => window.clearTimeout(timeout));
    return () => {
      active = false;
      controller.abort();
    };
  }, []);
  useEffect(() => {
    if (!API) return;
    let active = true;
    void apiClient.request<RiskEvidence>("/api/v1/risk/evidence")
      .then((evidence) => {
        if (active) {
          setRiskEvidence(evidence);
          setRiskEvidenceSource("api");
        }
      })
      .catch(() => {
        if (active) setRiskEvidenceSource("packaged");
      });
    return () => { active = false; };
  }, [apiClient]);
  useEffect(() => {
    if (!API || page !== "Analytics") return;
    let active = true;
    void apiClient.request<FleetAnalytics>("/api/v1/fleets/demo-fleet/analytics")
      .then((analytics) => {
        if (active) {
          setFleetAnalytics(analytics);
          setFleetAnalyticsSource("api");
        }
      })
      .catch(() => {
        if (active) setFleetAnalyticsSource("demo");
      });
    return () => { active = false; };
  }, [apiClient, page]);
  useEffect(() => {
    if (!trip.active || trip.paused) return;
    const timer = setInterval(
      () => setTrip((t) => ({ ...t, progress: Math.min(100, t.progress + 2) })),
      1000,
    );
    return () => clearInterval(timer);
  }, [trip.active, trip.paused]);
  useEffect(() => {
    if (!navigator.geolocation) {
      setLocationPermission("unsupported");
      return;
    }
    if (!navigator.permissions?.query) {
      setLocationPermission("prompt");
      return;
    }
    let permission: PermissionStatus | null = null;
    const updatePermission = () => {
      if (permission) setLocationPermission(permission.state);
    };
    void navigator.permissions
      .query({ name: "geolocation" })
      .then((status) => {
        permission = status;
        updatePermission();
        status.addEventListener("change", updatePermission);
      })
      .catch(() => setLocationPermission("prompt"));
    return () => permission?.removeEventListener("change", updatePermission);
  }, []);
  useEffect(() => {
    const controller = new AbortController();
    void fetchRouteWeather(defaultOrigin, defaultDestination, controller.signal)
      .then((conditions) => {
        setWeather(conditions);
        setWeatherStatus("ready");
        setRoutes((current) => applyWeatherRisk(current, conditions, "balanced"));
      })
      .catch(() => {
        if (!controller.signal.aborted) setWeatherStatus("unavailable");
      });
    return () => controller.abort();
  }, []);
  async function enrichRoutesWithWeather(
    routeOptions: RouteOption[],
    originPlace: ResolvedPlace,
    destinationPlace: ResolvedPlace,
  ) {
    setWeatherStatus("loading");
    try {
      const conditions = await fetchRouteWeather(originPlace, destinationPlace);
      setWeather(conditions);
      setWeatherStatus("ready");
      return applyWeatherRisk(routeOptions, conditions, preference);
    } catch {
      setWeather(null);
      setWeatherStatus("unavailable");
      return routeOptions;
    }
  }
  function useCurrentLocation() {
    if (!navigator.geolocation) {
      setNotice("Current location is not supported by this browser.");
      return;
    }
    setLocating(true);
    navigator.geolocation.getCurrentPosition(
      ({ coords }) => {
        const insideDemoArea =
          coords.latitude >= -34.36 &&
          coords.latitude <= -33.7 &&
          coords.longitude >= 18.28 &&
          coords.longitude <= 19.05;
        if (!insideDemoArea) {
          setNotice(
            "Your location is outside the Cape Town demonstration area. Search for a Cape Town origin instead.",
          );
          setLocating(false);
          return;
        }
        const place: ResolvedPlace = {
          displayName: `Current location (${coords.latitude.toFixed(5)}, ${coords.longitude.toFixed(5)})`,
          latitude: coords.latitude,
          longitude: coords.longitude,
        };
        setOrigin("Current location");
        setResolvedOrigin(place);
        setLocationPermission("granted");
        setNotice("Current location selected as the route origin.");
        setLocating(false);
      },
      (error) => {
        if (error.code === error.PERMISSION_DENIED) {
          setLocationPermission("denied");
        }
        setNotice(
          error.code === error.PERMISSION_DENIED
            ? "Location permission was denied. Enable it in your browser site settings or enter an origin manually."
            : "Your location could not be read. Enter a street, landmark or suburb instead.",
        );
        setLocating(false);
      },
      { enableHighAccuracy: true, timeout: 10_000, maximumAge: 60_000 },
    );
  }
  async function findRoutes() {
    setLoading(true);
    setNotice("");
    if (API) {
      try {
        await findApiRoutes();
        return;
      } catch {
        setNotice("The RoadSignal API is unavailable. Trying public routing services instead.");
      } finally {
        setLoading(false);
      }
    }
    await findPublicRoutes();
  }
  async function findPublicRoutes() {
    setLoading(true);
    try {
      const result = await analyseOpenRoutes(
        origin,
        destination,
        preference,
        incidents,
        resolvedOrigin,
        resolvedDestination,
      );
      const weatherAdjustedRoutes = await enrichRoutesWithWeather(
        result.routes,
        result.origin,
        result.destination,
      );
      setRoutes(weatherAdjustedRoutes);
      setSelected(
        weatherAdjustedRoutes.find((candidate) => candidate.recommended)?.id ??
          weatherAdjustedRoutes[0].id,
      );
      setResolvedOrigin(result.origin);
      setResolvedDestination(result.destination);
      setDataMode("public");
      setNotice(
        `Three public road alternatives found between ${result.origin.displayName.split(",")[0]} and ${result.destination.displayName.split(",")[0]}.`,
      );
    } catch (error) {
      if (error instanceof PlaceNotFoundError) setNotice(error.message);
      else useDemoRoutes("Live routing is unavailable. Built-in demonstration routes are shown instead.");
    } finally {
      setLoading(false);
    }
  }
  async function findApiRoutes() {
    setResolvedOrigin(null);
    setResolvedDestination(null);
    const controller = new AbortController();
    const timeout = window.setTimeout(() => controller.abort(), 8_000);
    try {
      const data = await apiClient.request<{ routes: ApiRoute[]; provider?: string }>("/api/v1/routes/analyse", {
        method: "POST",
        body: JSON.stringify({
          origin,
          destination,
          preference,
          departure_time: new Date().toISOString(),
          vehicle_type: "car",
        }),
        signal: controller.signal,
      });
      if (!data.routes.length) throw new Error("The API returned no route alternatives.");
      const apiRoutes = data.routes.map((r) => ({
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
      }));
      setRoutes(apiRoutes);
      setSelected(apiRoutes.find((candidate) => candidate.recommended)?.id ?? apiRoutes[0].id);
      setDataMode("api");
      setNotice(
        data.provider === "open"
          ? "Routes analysed by the RoadSignal API using live Nominatim/OSRM road data."
          : "Routes analysed by the RoadSignal API. Live map/routing services were unavailable, so the API served its built-in demonstration routes.",
      );
    } finally {
      window.clearTimeout(timeout);
    }
  }
  function useDemoRoutes(message = "Built-in demonstration routes are ready to explore.") {
    setRoutes(fallbackRoutes);
    setSelected("route-balanced");
    setResolvedOrigin(defaultOrigin);
    setResolvedDestination(defaultDestination);
    setDataMode("demo");
    setNotice(message);
    void enrichRoutesWithWeather(
      fallbackRoutes,
      defaultOrigin,
      defaultDestination,
    ).then(setRoutes);
  }
  async function startTrip() {
    if (API && dataMode === "api") {
      if (!session) {
        setNotice("Sign in before starting a protected live trip.");
        return;
      }
      setLoading(true);
      try {
        const liveTrip = await apiClient.request<{ id: string; progress: number; safety_score: number }>(
          `/api/v1/routes/${encodeURIComponent(route.id)}/start`,
          { method: "POST" },
        );
        setTrip({ id: liveTrip.id, active: true, paused: false, progress: liveTrip.progress, score: liveTrip.safety_score, alerts: [] });
        setNotice("Protected live trip started. Realtime risk updates are connected.");
      } catch (error) {
        setNotice(error instanceof Error ? error.message : "The live trip could not be started.");
        return;
      } finally {
        setLoading(false);
      }
    } else {
      setTrip({ active: true, paused: false, progress: 2, score: route.safetyScore, alerts: [] });
    }
    setPage("Live Trips");
    setAudit((a) => [`Trip started on ${route.name}`, ...a]);
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
        `${type} ahead. ${safestAlternative ? `${safestAlternative.name} is the lowest-risk available alternative.` : "Review the available alternatives."} Reroute recommended.`,
        ...t.alerts,
      ],
    }));
    setAudit((a) => [
      `${type} injected; route score recalculated; fleet alerted`,
      ...a,
    ]);
    setNotice(
      safestAlternative
        ? "Fleet alert published and safer reroute calculated."
        : "Fleet alert published. No safer alternative route is available.",
    );
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
          <p className="eyebrow">Friday, 17 July - Cape Town</p>
          <h1>Fleet operations overview</h1>
          <p>
            Real-time route-risk intelligence across demonstration operations.
          </p>
        </div>
        <button type="button" className="primary" onClick={() => setPage("Route Planner")}>
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
                Warning: {x}
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
          <div
            className={`location-permission ${locationPermission}`}
            aria-live="polite"
          >
            <div>
              <strong>
                {locationPermission === "granted"
                  ? "Location access enabled"
                  : locationPermission === "denied"
                    ? "Location access blocked"
                    : locationPermission === "unsupported"
                      ? "Location unavailable"
                      : "Enable current location"}
              </strong>
              <span>
                {locationPermission === "granted"
                  ? "Your browser can use your position as the route origin."
                  : locationPermission === "denied"
                    ? "Allow location in browser settings, or search manually."
                    : locationPermission === "unsupported"
                      ? "This browser does not expose geolocation; manual search still works."
                      : "Permission is requested only when you press Enable."}
              </span>
            </div>
            {locationPermission !== "granted" &&
              locationPermission !== "unsupported" && (
                <button
                  type="button"
                  onClick={useCurrentLocation}
                  disabled={locating || locationPermission === "checking"}
                >
                  {locating
                    ? "Locating..."
                    : locationPermission === "denied"
                      ? "Try again"
                      : "Enable"}
                </button>
              )}
          </div>
          <label>
            Origin
            <PlaceSearch
              value={origin}
              onChange={setOrigin}
              resolved={resolvedOrigin}
              onResolved={setResolvedOrigin}
              placeholder="Street, landmark or suburb"
            />
            <button
              className="location-button"
              type="button"
              onClick={useCurrentLocation}
              disabled={locating}
            >
              {locating ? "Locating..." : "Use current location"}
            </button>
          </label>
          <label>
            Destination
            <PlaceSearch
              value={destination}
              onChange={setDestination}
              resolved={resolvedDestination}
              onResolved={setResolvedDestination}
              placeholder="Street, landmark or suburb"
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
            <select
              value={preference}
              onChange={(event) =>
                setPreference(event.target.value as RoutePreference)
              }
            >
              <option value="balanced">Balanced</option>
              <option value="safest">Safest</option>
              <option value="fastest">Fastest</option>
            </select>
          </label>
          <button
            type="button"
            className="primary wide"
            onClick={findRoutes}
            disabled={loading}
          >
            {loading ? "Resolving places and road routes..." : "Find routes"}
          </button>
          <button className="demo-route-button" type="button" onClick={() => useDemoRoutes()}>
            Use built-in demo routes
          </button>
          <p className="routing-attribution">
            Search by{" "}
            <a href="https://photon.komoot.io" target="_blank" rel="noreferrer">
              Photon
            </a>
            {" - "}routing by{" "}
            <a
              href="https://routing.openstreetmap.de/about.html"
              target="_blank"
              rel="noreferrer"
            >
              OSRM/FOSSGIS
            </a>
            {" - "}
            <a
              href="https://www.openstreetmap.org/copyright"
              target="_blank"
              rel="noreferrer"
            >
               OpenStreetMap contributors
            </a>
          </p>
        </section>
        <MapView routes={routes} selected={selected} />
      </div>
      <section className={`weather-strip ${weatherStatus}`} aria-live="polite" aria-busy={weatherStatus === "loading"}>
        <div className="weather-heading">
          <span className="weather-symbol" aria-hidden="true">WX</span>
          <div><h2>Route weather</h2><p>Current conditions near the route corridor</p></div>
        </div>
        {weatherStatus === "loading" ? (
          <p className="weather-message">Checking current conditions...</p>
        ) : weatherStatus === "unavailable" || !weather ? (
          <div className="weather-message">
            <span>Weather is temporarily unavailable. Route planning still works without it.</span>
            <button type="button" onClick={() => void enrichRoutesWithWeather(routes, resolvedOrigin ?? defaultOrigin, resolvedDestination ?? defaultDestination).then(setRoutes)}>Retry weather</button>
          </div>
        ) : (
          <>
            <dl className="weather-readings">
              <div><dt>Conditions</dt><dd>{weather.condition}</dd></div>
              <div><dt>Temperature</dt><dd>{Math.round(weather.temperatureC)}&deg;C</dd></div>
              <div><dt>Feels like</dt><dd>{Math.round(weather.apparentTemperatureC)}&deg;C</dd></div>
              <div><dt>Wind</dt><dd>{Math.round(weather.windSpeedKmh)} km/h</dd></div>
              <div><dt>Visibility</dt><dd>{weather.visibilityKm} km</dd></div>
              <div><dt>Weather risk</dt><dd className={`weather-risk ${weather.riskLabel.toLowerCase()}`}>{weather.riskLabel}</dd></div>
            </dl>
            <p className="weather-source">Live data by <a href="https://open-meteo.com/" target="_blank" rel="noreferrer">Open-Meteo</a>. No API key, cookies, or precise device location is sent.</p>
          </>
        )}
      </section>
      <div className="route-grid">
        {routes.map((r) => (
          <button
            type="button"
            className={`route-card ${selected === r.id ? "selected" : ""}`}
            onClick={() => setSelected(r.id)}
            key={r.id}
            aria-pressed={selected === r.id}
            aria-label={`${r.name}: ${r.durationMinutes} minutes, ${r.distanceKm} kilometres, safety estimate ${r.safetyScore} out of 100`}
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
        <button type="button" className="primary" onClick={startTrip}>
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
          <p>
            {resolvedOrigin?.displayName.split(",")[0] ?? origin} to{" "}
            {resolvedDestination?.displayName.split(",")[0] ?? destination}
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
          {trip.alerts.map((x) => (
            <div className="alert danger-bg" key={x}>
              <strong>Reroute recommended</strong>
              <br />
              {x}
              {safestAlternative && (
                <button
                  type="button"
                  onClick={() => {
                    setSelected(safestAlternative.id);
                    setTrip((t) => ({
                      ...t,
                      score: safestAlternative.safetyScore,
                      alerts: [],
                    }));
                    setAudit((a) => [
                      `Reroute accepted via ${safestAlternative.name}`,
                      ...a,
                    ]);
                  }}
                >
                  Accept safer route
                </button>
              )}
            </div>
          ))}
          <div className="actions">
            <button
              type="button"
              onClick={() => setTrip((t) => ({ ...t, paused: !t.paused }))}
            >
              {trip.paused ? "Resume" : "Pause"}
            </button>
            <button type="button" onClick={() => inject("Accident")}>
              Simulate accident
            </button>
            <button type="button" onClick={() => inject("Crime report")}>
              Simulate crime
            </button>
            <button
              type="button"
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
            Development simulator - events are demonstration data
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
        <button type="button" className="primary" onClick={() => inject("Road closure")}>
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
            {incidents.map((i) => (
              <tr key={i.id}>
                <td data-label="Incident">
                  <strong>{i.incidentType}</strong>
                  <small>{i.description}</small>
                </td>
                <td data-label="Severity">
                  <span className={`severity s${i.severity}`}>
                    {i.severity}
                  </span>
                </td>
                <td data-label="Reported">{new Date(i.occurredAt).toLocaleTimeString()}</td>
                <td data-label="Source">{i.sourceType}</td>
                <td data-label="Confidence">{Math.round(i.confidence * 100)}%</td>
                <td data-label="Verification">
                  {i.verificationStatus}
                  <small>
                    {i.confirmations} confirms - {i.disputes} disputes
                  </small>
                </td>
                <td data-label="Actions">
                  <button type="button" onClick={() => moderate(i.id, "confirmations")}>
                    Confirm
                  </button>
                  <button type="button" onClick={() => moderate(i.id, "disputes")}>
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
          <p className="eyebrow">Last 30 days - Demonstration data</p>
          <h1>{page}</h1>
          <p>Operational safety performance and confidence-weighted trends.</p>
        </div>
        <span className={`evidence-source ${fleetAnalyticsSource}`}>
          {fleetAnalyticsSource === "api" ? "Live from API" : "Demo data"}
        </span>
      </section>
      <div className="metrics">
        <Metric label="Average safety" value={fleetAnalytics.average_safety_score.toFixed(1)} />
        <Metric label="Active drivers" value={fleetAnalytics.active_drivers} />
        <Metric label="Active incidents" value={fleetAnalytics.active_incidents} />
        <Metric label="Trips completed today" value={fleetAnalytics.trips_completed_today} />
        <Metric label="High-risk drivers" value={fleetAnalytics.high_risk_drivers} />
        <Metric label="Reroutes triggered" value="38" />
        <Metric label="Recommendations accepted" value="74%" />
      </div>
      <div className="grid two">
        <section className="panel">
          <h2>Safety score by hour</h2>
          <div className="chart" role="img" aria-label="Hourly safety estimates range from 69 to 88, ending at 88">
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
  const evidencePage = (
    <>
      <section className="heading evidence-heading">
        <div>
          <p className="eyebrow">Reproducible risk governance</p>
          <h1>Risk evidence</h1>
          <p>See what the scoring method can prove, what it cannot, and why training is blocked.</p>
        </div>
        <span className={`evidence-source ${riskEvidenceSource}`}>
          {riskEvidenceSource === "api" ? "Verified by API" : "Packaged evidence"}
        </span>
      </section>
      <section className="evidence-hero" aria-labelledby="evidence-status-title">
        <div className="evidence-verdict">
          <span aria-hidden="true">Baseline 1.0</span>
          <h2 id="evidence-status-title">No trained safety model</h2>
          <p>{riskEvidence.claims.summary}</p>
        </div>
        <dl className="evidence-facts">
          <div><dt>Method</dt><dd>Transparent weighted baseline</dd></div>
          <div><dt>Training gate</dt><dd>Blocked</dd></div>
          <div><dt>Artifact emitted</dt><dd>No</dd></div>
          <div><dt>Hash verified</dt><dd>{riskEvidence.evaluation.sha256_verified ? "Yes" : "No"}</dd></div>
        </dl>
      </section>
      <div className="evidence-layout">
        <section className="evidence-section" aria-labelledby="evaluation-title">
          <div className="evidence-section-heading">
            <div>
              <p className="eyebrow">Synthetic evaluation only</p>
              <h2 id="evaluation-title">Baseline evaluation</h2>
            </div>
            <span>{riskEvidence.evaluation.license}</span>
          </div>
          <dl className="evidence-metrics">
            <div><dt>Validated rows</dt><dd>{riskEvidence.evaluation.rows}</dd></div>
            <div><dt>Held-out rows</dt><dd>{riskEvidence.evaluation.test_rows}</dd></div>
            <div><dt>Brier score</dt><dd>{riskEvidence.evaluation.brier.toFixed(3)}</dd></div>
            <div><dt>Calibration error</dt><dd>{riskEvidence.evaluation.expected_calibration_error.toFixed(3)}</dd></div>
          </dl>
          <p className="evidence-note">
            AUC {riskEvidence.evaluation.auc?.toFixed(3) ?? "not available"} is shown for pipeline verification only. The small synthetic holdout cannot establish real-world accuracy.
          </p>
        </section>
        <section className="evidence-section gate" aria-labelledby="gate-title">
          <p className="eyebrow">Fail-closed decision</p>
          <h2 id="gate-title">Why training stops here</h2>
          <ul className="gate-list">
            {riskEvidence.training_gate.blockers.map((blocker) => <li key={blocker}>{blocker}</li>)}
          </ul>
          <p>A future candidate needs licensed outcome data, temporal and geographic holdouts, calibration, subgroup review, monitoring, and rollback evidence.</p>
        </section>
      </div>
      <section className="evidence-controls" aria-labelledby="controls-title">
        <div>
          <p className="eyebrow">Engineering controls</p>
          <h2 id="controls-title">Evidence before algorithms</h2>
        </div>
        <ul>
          <li><strong>Provenance</strong><span>Source, licence, permitted use, coverage, and SHA-256 digest</span></li>
          <li><strong>Leakage</strong><span>Prediction-time feature contract and chronological partitions</span></li>
          <li><strong>Quality</strong><span>Schema, coordinates, missingness, duplicates, ranges, and class checks</span></li>
          <li><strong>Evaluation</strong><span>Calibration and geographic plus day/night subgroups</span></li>
        </ul>
      </section>
      <p className="evidence-disclaimer">{riskEvidence.claims.disclaimer}</p>
    </>
  );
  if (!entered) {
    return (
      <EntryGate
        client={apiClient}
        onSession={(next) => {
          setSession(next);
          setEntered(true);
        }}
        onGuest={() => setEntered(true)}
      />
    );
  }
  return (
    <>
      <a className="skip-link" href="#main-content">Skip to main content</a>
      <div className="shell">
      <aside aria-label="RoadSignal navigation">
        <div className="brand">
          <b>SR</b>
          <span>
            RoadSignal
            <small>Route-risk intelligence</small>
          </span>
        </div>
        <nav aria-label="Application sections">
          {nav.map((n) => (
            <button
              className={page === n ? "active" : ""}
              onClick={() => setPage(n)}
              key={n}
              type="button"
              aria-current={page === n ? "page" : undefined}
            >
              <i aria-hidden="true">{navIcons[n as keyof typeof navIcons]}</i>
              {n}
              {n === "Incidents" && <em>{incidents.length}</em>}
            </button>
          ))}
        </nav>
      </aside>
      <main id="main-content" tabIndex={-1}>
        <section className="demo-banner" aria-label="Demonstration status">
          <div>
            <strong>GitHub Pages demonstration</strong>
            <span>
              This showcase uses {dataMode === "public" ? "public map and road services" : dataMode === "api" ? "the configured API" : "built-in simulated data"}. It is decision support, not a guarantee of safety.
            </span>
          </div>
          <div className="connection-badges" aria-live="polite">
            <span className={`mode-badge ${dataMode}`}>
              {dataMode === "public" ? "Public data" : dataMode === "api" ? "API connected" : "Demo data"}
            </span>
            {API && <span className={`realtime-badge ${realtimeStatus}`}>Realtime: {realtimeStatus}</span>}
            {API && backendStatus === "waking" && (
              <span className="realtime-badge connecting">Backend: waking up (can take up to a minute)</span>
            )}
            {API && backendStatus === "unavailable" && (
              <span className="realtime-badge disconnected">Backend: unavailable, using public/demo data</span>
            )}
          </div>
        </section>
        {API && <AuthPanel client={apiClient} session={session} onSession={setSession} />}
        {notice && (
          <div className="toast" role="status" aria-live="polite">
            <span>{notice}</span>
            <button type="button" onClick={() => setNotice("")} aria-label="Dismiss notification">Close</button>
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
                : page === "Settings"
                  ? evidencePage
                  : analyticsPage}
      </main>
    </div>
    </>
  );
}
