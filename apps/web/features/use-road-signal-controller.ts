import { useEffect, useMemo, useState } from "react";
import type { Incident, RouteOption, RoutePreference } from "@roadsignal/types";
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
import { RoadSignalApiClient, type SessionSnapshot } from "../lib/api-client";
import {
  defaultDestination,
  defaultOrigin,
  demoDrivers,
  fallbackRoutes,
  initialIncidents,
} from "./demo-data";
import type { AppPage } from "./operations/operations-pages";
import { useBackendData } from "./use-backend-data";

export const API =
  process.env.NEXT_PUBLIC_API_URL ??
  (process.env.NODE_ENV === "development" ? "http://localhost:8000" : "");

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
  breakdown: {
    crime: number;
    accident: number;
    traffic: number;
    weather: number;
    road_condition: number;
    community: number;
  };
  explanation: string;
  geometry: RouteOption["geometry"];
};
type WeatherStatus = "loading" | "ready" | "unavailable";
type LocationPermissionStatus =
  | "checking"
  | "prompt"
  | "granted"
  | "denied"
  | "unsupported";

export function useRoadSignalController() {
  const [page, setPage] = useState<AppPage>("Dashboard"),
    [routes, setRoutes] = useState(fallbackRoutes),
    [selected, setSelected] = useState("route-balanced"),
    [loading, setLoading] = useState(false),
    [locating, setLocating] = useState(false),
    [locationPermission, setLocationPermission] =
      useState<LocationPermissionStatus>("checking"),
    [notice, setNotice] = useState(""),
    [dataMode, setDataMode] = useState<DataMode>("demo"),
    [weather, setWeather] = useState<RouteWeather | null>(null),
    [weatherStatus, setWeatherStatus] = useState<WeatherStatus>("loading");
  const apiClient = useMemo(() => new RoadSignalApiClient(API), []);
  const [session, setSession] = useState<SessionSnapshot | null>(null);
  const [entered, setEntered] = useState(false);
  const [analyticsWindow, setAnalyticsWindow] = useState<"7" | "30" | "90">(
    "30",
  );
  const [fleetQuery, setFleetQuery] = useState("");
  const [fleetStatus, setFleetStatus] = useState("All statuses");
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
  const visibleDrivers = demoDrivers.filter((driver) => {
    const matchesQuery = `${driver.name} ${driver.vehicle} ${driver.route}`
      .toLowerCase()
      .includes(fleetQuery.trim().toLowerCase());
    return (
      matchesQuery &&
      (fleetStatus === "All statuses" || driver.status === fleetStatus)
    );
  });
  const {
    realtimeStatus,
    backendStatus,
    riskEvidence,
    riskEvidenceSource,
    fleetAnalytics,
    fleetAnalyticsSource,
  } = useBackendData({
    apiUrl: API,
    apiClient,
    accessToken: session?.accessToken,
    page,
    onRealtimeEvents: (events) => {
      setAudit((current) => [
        ...events.map((event) => `${event.type.replaceAll(".", " ")}: live API event received`),
        ...current,
      ].slice(0, 100));
      if (events.some((event) => event.type === "route.risk_changed")) {
        setNotice("Live route risk changed. Review the active trip and available alternatives.");
      }
    },
  });
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
        setRoutes((current) =>
          applyWeatherRisk(current, conditions, "balanced"),
        );
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
        setNotice(
          "The RoadSignal API is unavailable. Trying public routing services instead.",
        );
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
      else
        useDemoRoutes(
          "Live routing is unavailable. Built-in demonstration routes are shown instead.",
        );
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
      const data = await apiClient.request<{
        routes: ApiRoute[];
        provider?: string;
      }>("/api/v1/routes/analyse", {
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
      if (!data.routes.length)
        throw new Error("The API returned no route alternatives.");
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
      setSelected(
        apiRoutes.find((candidate) => candidate.recommended)?.id ??
          apiRoutes[0].id,
      );
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
  function useDemoRoutes(
    message = "Built-in demonstration routes are ready to explore.",
  ) {
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
        const liveTrip = await apiClient.request<{
          id: string;
          progress: number;
          safety_score: number;
        }>(`/api/v1/routes/${encodeURIComponent(route.id)}/start`, {
          method: "POST",
        });
        setTrip({
          id: liveTrip.id,
          active: true,
          paused: false,
          progress: liveTrip.progress,
          score: liveTrip.safety_score,
          alerts: [],
        });
        setNotice(
          "Protected live trip started. Realtime risk updates are connected.",
        );
      } catch (error) {
        setNotice(
          error instanceof Error
            ? error.message
            : "The live trip could not be started.",
        );
        return;
      } finally {
        setLoading(false);
      }
    } else {
      setTrip({
        active: true,
        paused: false,
        progress: 2,
        score: route.safetyScore,
        alerts: [],
      });
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
  return {
    page,
    setPage,
    routes,
    setRoutes,
    selected,
    setSelected,
    loading,
    locating,
    locationPermission,
    notice,
    setNotice,
    dataMode,
    weather,
    weatherStatus,
    realtimeStatus,
    backendStatus,
    apiClient,
    session,
    setSession,
    entered,
    setEntered,
    riskEvidence,
    riskEvidenceSource,
    fleetAnalytics,
    fleetAnalyticsSource,
    analyticsWindow,
    setAnalyticsWindow,
    fleetQuery,
    setFleetQuery,
    fleetStatus,
    setFleetStatus,
    trip,
    setTrip,
    incidents,
    origin,
    setOrigin,
    destination,
    setDestination,
    preference,
    setPreference,
    resolvedOrigin,
    setResolvedOrigin,
    resolvedDestination,
    setResolvedDestination,
    audit,
    setAudit,
    route,
    safestAlternative,
    visibleDrivers,
    enrichRoutesWithWeather,
    useCurrentLocation,
    findRoutes,
    useDemoRoutes,
    startTrip,
    inject,
    moderate,
  };
}
