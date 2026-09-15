"use client";

import type { Incident, RouteOption } from "@roadsignal/types";
import type { GeoJSONSource, Map as MapLibreMap, Marker } from "maplibre-gl";
import { useEffect, useId, useMemo, useRef, useState } from "react";
import type { RouteWeather } from "../lib/open-weather";
import { cellProvenance, type MapCellsState } from "../lib/map-cells";
import { SEVERE_WEATHER_LABELS, type CctvCamera, type HazardLayerState, type SevereWeatherEvent, type WildfireHotspot } from "../lib/hazards";
import { useTelemetryMarkers, type MapTelemetry } from "./telemetry-markers";

const OPEN_STYLE = "https://tiles.openfreemap.org/styles/liberty";
const ROUTE_SOURCE = "roadsignal-routes";
const ROUTE_HIT_LAYER = "roadsignal-route-hits";
const ROUTE_LAYER = "roadsignal-route-lines";
const CELL_SOURCE = "roadsignal-incident-cells";
const CELL_LAYER = "roadsignal-incident-cell-fill";
const CELL_OUTLINE = "roadsignal-incident-cell-outline";
const WILDFIRE_SOURCE = "roadsignal-wildfires";
const WILDFIRE_LAYER = "roadsignal-wildfire-points";
const WEATHER_SOURCE = "roadsignal-severe-weather";
const WEATHER_LAYER = "roadsignal-severe-weather-points";
const CAMERA_SOURCE = "roadsignal-cameras";
const CAMERA_LAYER = "roadsignal-camera-points";
const EMPTY_INCIDENTS: Incident[] = [];
const EMPTY_FEATURE_COLLECTION = { type: "FeatureCollection" as const, features: [] };

export type HazardLayers = {
  wildfires: HazardLayerState<WildfireHotspot>;
  severeWeather: HazardLayerState<SevereWeatherEvent>;
  cameras: HazardLayerState<CctvCamera>;
};

type Props = {
  routes: RouteOption[];
  selected: string;
  progress?: number;
  weather?: RouteWeather | null;
  weatherStatus?: "loading" | "ready" | "unavailable";
  incidents?: Incident[];
  onSelectRoute?: (routeId: string) => void;
  cells?: MapCellsState;
  hazards?: HazardLayers;
  telemetry?: MapTelemetry;
};
type MapStatus = "loading" | "ready" | "failed";

function riskColour(score: number) {
  return score >= 80 ? "#178652" : score >= 60 ? "#c47a0c" : "#c33d3d";
}

function routeFeatures(routes: RouteOption[], selected: string, telemetry = false) {
  const ordered = [...routes].sort(
    (a, b) => Number(a.id === selected) - Number(b.id === selected),
  );
  return {
    type: "FeatureCollection" as const,
    features: ordered.flatMap((route) =>
      route.geometry.slice(0, -1).map((point, index) => {
        const next = route.geometry[index + 1];
        const segmentScore = Math.max(
          25,
          route.safetyScore - (index === 1 ? 18 : index % 2 === 0 ? 2 : 8),
        );
        return {
          type: "Feature" as const,
          properties: {
            routeId: route.id,
            routeName: route.name,
            safetyScore: route.safetyScore,
            durationMinutes: route.durationMinutes,
            colour: telemetry ? (route.id === selected ? "#b89500" : "#7f9187") :
              route.id === selected
                ? riskColour(segmentScore)
                : route.id === "route-balanced"
                  ? "#d4b600"
                  : route.id === "route-safest"
                    ? "#1f9d61"
                    : "#d45545",
            width: route.id === selected ? 7 : 3,
            opacity: route.id === selected ? 0.95 : 0.3,
          },
          geometry: {
            type: "LineString" as const,
            coordinates: [
              [point.longitude, point.latitude],
              [next.longitude, next.latitude],
            ],
          },
        };
      }),
    ),
  };
}

/** i-traffic serves a fresh JPEG per request; a changing param defeats the cache. */
function cameraFrameUrl(url: string, frame: number) {
  if (!frame) return url;
  return `${url}${url.includes("?") ? "&" : "?"}t=${frame}`;
}

function ExpandIcon({ expanded }: { expanded: boolean }) {
  return (
    <svg width="16" height="16" viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.9" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      {expanded ? (
        <>
          <path d="M9 3H4v5" />
          <path d="M11 17h5v-5" />
          <path d="M4 3l5 5" />
          <path d="M16 17l-5-5" />
        </>
      ) : (
        <>
          <path d="M12 2h6v6" />
          <path d="M8 18H2v-6" />
          <path d="M18 2l-7 7" />
          <path d="M2 18l7-7" />
        </>
      )}
    </svg>
  );
}

function wildfireFeatures(hotspots: WildfireHotspot[]) {
  return {
    type: "FeatureCollection" as const,
    features: hotspots.map((hotspot, index) => ({
      type: "Feature" as const,
      properties: { index },
      geometry: { type: "Point" as const, coordinates: [hotspot.longitude, hotspot.latitude] },
    })),
  };
}

function severeWeatherFeatures(events: SevereWeatherEvent[]) {
  return {
    type: "FeatureCollection" as const,
    features: events.map((event) => ({
      type: "Feature" as const,
      properties: { id: event.id, category: event.category },
      geometry: { type: "Point" as const, coordinates: [event.longitude, event.latitude] },
    })),
  };
}

function cameraFeatures(cameras: CctvCamera[]) {
  return {
    type: "FeatureCollection" as const,
    features: cameras.map((camera) => ({
      type: "Feature" as const,
      properties: { id: camera.id },
      geometry: { type: "Point" as const, coordinates: [camera.longitude, camera.latitude] },
    })),
  };
}

function pointAtProgress(route: RouteOption | undefined, progress: number) {
  if (!route || route.geometry.length < 2) return null;
  const scaled =
    (Math.max(0, Math.min(progress, 100)) / 100) * (route.geometry.length - 1);
  const index = Math.min(Math.floor(scaled), route.geometry.length - 2);
  const fraction = scaled - index;
  const start = route.geometry[index];
  const end = route.geometry[index + 1];
  return [
    start.longitude + (end.longitude - start.longitude) * fraction,
    start.latitude + (end.latitude - start.latitude) * fraction,
  ] as [number, number];
}

function incidentLabel(incident: Incident) {
  return `${incident.incidentType}, severity ${incident.severity} of 5, ${Math.round(incident.confidence * 100)}% confidence`;
}

function SchematicFallback({
  routes,
  selected,
  progress = 0,
  incidents = EMPTY_INCIDENTS,
  onSelectRoute,
  onPreviewRoute,
  onSelectIncident,
  telemetry,
}: Props & {
  onPreviewRoute: (routeId: string | null) => void;
  onSelectIncident: (incidentId: string) => void;
}) {
  const colours: Record<string, string> = {
    "route-balanced": "#d4b600",
    "route-safest": "#1f9d61",
    "route-fastest": "#d45545",
  };
  const activeIncidents = incidents.filter((incident) => incident.status === "active");
  const allPoints = [
    ...routes.flatMap((route) => route.geometry),
    ...activeIncidents.map((incident) => incident.location),
    ...(telemetry ? [...telemetry.vehicles, ...telemetry.sensors].map((reading) => reading.position) : []),
  ];
  const west = Math.min(...allPoints.map((point) => point.longitude));
  const east = Math.max(...allPoints.map((point) => point.longitude));
  const south = Math.min(...allPoints.map((point) => point.latitude));
  const north = Math.max(...allPoints.map((point) => point.latitude));
  const longitudeSpan = Math.max(east - west, 0.01);
  const latitudeSpan = Math.max(north - south, 0.01);
  const project = ([longitude, latitude]: [number, number]) =>
    [
      38 + ((longitude - west) / longitudeSpan) * 444,
      36 + ((north - latitude) / latitudeSpan) * 228,
    ] as const;
  const points = (route: RouteOption) =>
    route.geometry
      .map((point) => project([point.longitude, point.latitude]).join(","))
      .join(" ");
  const activeRoute = routes.find((route) => route.id === selected);
  const driverPoint = pointAtProgress(activeRoute, progress);
  const projectedDriver = driverPoint ? project(driverPoint) : null;
  const origin = activeRoute?.geometry[0];
  const destination = activeRoute?.geometry.at(-1);
  const projectedOrigin = origin ? project([origin.longitude, origin.latitude]) : null;
  const projectedDestination = destination
    ? project([destination.longitude, destination.latitude])
    : null;

  const selectFromKeyboard = (
    event: React.KeyboardEvent<SVGGElement>,
    routeId: string,
  ) => {
    if (event.key === "Enter" || event.key === " ") {
      event.preventDefault();
      onSelectRoute?.(routeId);
    }
  };

  return (
    <svg
      className="map-fallback"
      viewBox="0 0 520 300"
      preserveAspectRatio={telemetry ? "xMidYMid meet" : "xMidYMid slice"}
      role="group"
      aria-label="Offline schematic route map"
    >
      <rect width="520" height="300" fill="#e8ece8" />
      <path
        d="M0 0H520V70C445 92 403 66 339 87C271 109 239 77 181 91C116 107 74 78 0 98Z"
        fill="#d6e5e8"
      />
      <g stroke="#c8cfcb" strokeWidth="5" fill="none" opacity=".9">
        <path d="M-20 254C92 222 162 157 276 147S430 93 548 52" />
        <path d="M-30 111C76 130 143 193 246 198S410 244 545 276" />
        <path d="M105 -20C135 65 195 117 226 184S255 258 282 330" />
      </g>
      <g stroke="#f6f7f3" strokeWidth="2" fill="none" opacity=".95">
        <path d="M18 205L482 112" />
        <path d="M46 276L440 34" />
        <path d="M168 8L348 294" />
      </g>
      {routes.map((route) => (
        <g
          className="schematic-route"
          key={route.id}
          role="button"
          tabIndex={0}
          aria-pressed={selected === route.id}
          aria-label={`Select ${route.name}: ${route.durationMinutes} minutes, safety estimate ${route.safetyScore} out of 100`}
          onClick={() => onSelectRoute?.(route.id)}
          onKeyDown={(event) => selectFromKeyboard(event, route.id)}
          onMouseEnter={() => onPreviewRoute(route.id)}
          onMouseLeave={() => onPreviewRoute(null)}
          onFocus={() => onPreviewRoute(route.id)}
          onBlur={() => onPreviewRoute(null)}
        >
          <polyline
            className="schematic-route-hit"
            points={points(route)}
            fill="none"
            stroke="transparent"
            strokeWidth="24"
            vectorEffect="non-scaling-stroke"
          />
          <polyline
            className="schematic-route-line"
            points={points(route)}
            fill="none"
            stroke={telemetry ? (selected === route.id ? "#b89500" : "#7f9187") : colours[route.id] ?? riskColour(route.safetyScore)}
            strokeWidth={selected === route.id ? 9 : 4}
            opacity={selected === route.id ? 1 : 0.35}
            strokeLinecap="round"
            strokeLinejoin="round"
            vectorEffect="non-scaling-stroke"
          />
        </g>
      ))}
      {projectedOrigin && (
        <g className="schematic-endpoint" aria-hidden="true">
          <circle cx={projectedOrigin[0]} cy={projectedOrigin[1]} r="10" />
          <text x={projectedOrigin[0]} y={projectedOrigin[1] + 4}>A</text>
        </g>
      )}
      {projectedDestination && (
        <g className="schematic-endpoint destination" aria-hidden="true">
          <circle cx={projectedDestination[0]} cy={projectedDestination[1]} r="10" />
          <text x={projectedDestination[0]} y={projectedDestination[1] + 4}>B</text>
        </g>
      )}
      {activeIncidents.map((incident) => {
        const point = project([incident.location.longitude, incident.location.latitude]);
        return (
          <g
            className={`schematic-incident severity-${incident.severity}`}
            key={incident.id}
            role="button"
            tabIndex={0}
            aria-label={incidentLabel(incident)}
            transform={`translate(${point[0]} ${point[1]})`}
            onClick={() => onSelectIncident(incident.id)}
            onKeyDown={(event) => {
              if (event.key === "Enter" || event.key === " ") {
                event.preventDefault();
                onSelectIncident(incident.id);
              }
            }}
          >
            <circle r="12" />
            <text y="4">!</text>
          </g>
        );
      })}
      {projectedDriver && !telemetry && (
        <circle
          cx={projectedDriver[0]}
          cy={projectedDriver[1]}
          r="9"
          fill="#ffda00"
          stroke="#20211d"
          strokeWidth="4"
          aria-hidden="true"
        />
      )}
      {telemetry && [...telemetry.sensors, ...telemetry.vehicles].map((reading) => {
        const point = project([reading.position.longitude, reading.position.latitude]);
        const vehicle = "driver" in reading;
        const isSelected = vehicle ? telemetry.selectedVehicle === reading.id : telemetry.selectedSensor === reading.id;
        const select = () => vehicle ? telemetry.onSelectVehicle(reading.id) : telemetry.onSelectSensor(reading.id);
        return <g key={reading.id} role="button" tabIndex={0} aria-pressed={isSelected}
          aria-label={vehicle ? `Demo tracker ${reading.id}, ${reading.state}` : `Demo sensor ${reading.name}, ${reading.state}`}
          className={`schematic-telemetry ${vehicle ? "vehicle" : "sensor"} ${reading.state}${isSelected ? " is-selected" : ""}`}
          style={{ transform: `translate(${point[0]}px, ${point[1]}px)`, transitionDuration: telemetry.animating ? "900ms" : "0ms" }}
          onClick={select} onKeyDown={(event) => { if (event.key === "Enter" || event.key === " ") { event.preventDefault(); select(); } }}>
          <rect className="telemetry-hit-target" x="-13" y="-13" width="26" height="26" rx={vehicle ? 13 : 4} vectorEffect="non-scaling-stroke" />
          <rect x="-13" y="-13" width="26" height="26" rx={vehicle ? 13 : 4} />
          <text y="4">{vehicle ? reading.label : reading.id}</text>
        </g>;
      })}
    </svg>
  );
}

function modelTime(value: string) {
  const time = value.split("T")[1]?.slice(0, 5);
  return time || "time unavailable";
}

function WeatherReadout({
  weather,
  status,
}: {
  weather?: RouteWeather | null;
  status?: Props["weatherStatus"];
}) {
  if (!status) return null;
  if (status === "loading") {
    return <div className="map-weather message loading" role="status">Checking route weather...</div>;
  }
  if (status === "unavailable" || !weather) {
    return <div className="map-weather message unavailable" role="status">Weather model unavailable</div>;
  }
  return (
    <section
      className={`map-weather ${weather.riskLabel.toLowerCase()}`}
      aria-label="Three-point route weather model estimate"
    >
      <header>
        <strong>{weather.condition}</strong>
        <span>{weather.riskLabel} weather risk</span>
      </header>
      <dl>
        <div><dt>Temperature</dt><dd>{Math.round(weather.temperatureC)}&deg;C</dd></div>
        <div><dt>Rain</dt><dd>{weather.precipitationMm.toFixed(1)} mm</dd></div>
        <div><dt>Wind</dt><dd>{Math.round(weather.windSpeedKmh)} km/h</dd></div>
        <div><dt>Visibility</dt><dd>{weather.visibilityKm} km</dd></div>
      </dl>
      <div className="map-weather-samples" aria-label="Route weather samples">
        {weather.samples.map((sample) => (
          <span key={sample.label}>
            <i className={`weather-sample-dot ${sample.riskLabel.toLowerCase()}`} />
            {sample.label === "Mid-route" ? "Mid" : sample.label} {Math.round(sample.temperatureC)}&deg;
          </span>
        ))}
      </div>
      <small>
        Highest exposure: {weather.highestRiskAt.toLowerCase()} · model time {modelTime(weather.observedAt)}
      </small>
    </section>
  );
}

function incidentTime(value: string) {
  const date = new Date(value);
  if (Number.isNaN(date.valueOf())) return "Time unavailable";
  return new Intl.DateTimeFormat("en-ZA", {
    day: "numeric",
    month: "short",
    hour: "2-digit",
    minute: "2-digit",
  }).format(date);
}

function IncidentDetail({ incident, onClose }: { incident: Incident; onClose: () => void }) {
  return (
    <aside className="map-incident-detail" aria-label={`${incident.incidentType} details`}>
      <header>
        <div><span>Active incident</span><strong>{incident.incidentType}</strong></div>
        <button type="button" onClick={onClose} aria-label="Close incident details">Close</button>
      </header>
      <p>{incident.description}</p>
      <dl>
        <div><dt>Severity</dt><dd>{incident.severity}/5</dd></div>
        <div><dt>Confidence</dt><dd>{Math.round(incident.confidence * 100)}%</dd></div>
        <div><dt>Status</dt><dd>{incident.verificationStatus}</dd></div>
        <div><dt>Reported</dt><dd>{incidentTime(incident.occurredAt)}</dd></div>
      </dl>
      <small>Source: {incident.sourceType.replaceAll("_", " ")}</small>
    </aside>
  );
}

export function RouteMap({
  routes,
  selected,
  progress = 0,
  weather,
  weatherStatus,
  incidents = EMPTY_INCIDENTS,
  onSelectRoute,
  cells,
  hazards,
  telemetry,
}: Props) {
  const summaryId = useId();
  const container = useRef<HTMLDivElement>(null);
  const map = useRef<MapLibreMap | null>(null);
  const driverMarker = useRef<Marker | null>(null);
  const incidentMarkers = useRef<Marker[]>([]);
  const endpointMarkers = useRef<Marker[]>([]);
  const onSelectRouteRef = useRef(onSelectRoute);
  const [status, setStatus] = useState<MapStatus>("loading");
  const [previewRouteId, setPreviewRouteId] = useState<string | null>(null);
  const [selectedIncidentId, setSelectedIncidentId] = useState<string | null>(null);
  const [showCells, setShowCells] = useState(false);
  const [selectedCellId, setSelectedCellId] = useState<string | null>(null);
  const [showWildfires, setShowWildfires] = useState(false);
  const [showSevereWeather, setShowSevereWeather] = useState(false);
  const [showCameras, setShowCameras] = useState(false);
  const [selectedWildfireIndex, setSelectedWildfireIndex] = useState<number | null>(null);
  const [selectedWeatherId, setSelectedWeatherId] = useState<string | null>(null);
  const [selectedCameraId, setSelectedCameraId] = useState<string | null>(null);
  const [expanded, setExpanded] = useState(false);
  const [cameraExpanded, setCameraExpanded] = useState(false);
  const [cameraFrame, setCameraFrame] = useState(0);
  useTelemetryMarkers(map, status === "ready", telemetry);
  const selectedCell = cells?.data?.features.find((cell) => cell.id === selectedCellId);
  const selectedWildfire = selectedWildfireIndex != null ? hazards?.wildfires.data[selectedWildfireIndex] : undefined;
  const selectedWeatherEvent = hazards?.severeWeather.data.find((event) => event.id === selectedWeatherId);
  const selectedCamera = hazards?.cameras.data.find((camera) => camera.id === selectedCameraId);
  const clearHazardSelections = () => {
    setSelectedWildfireIndex(null);
    setSelectedWeatherId(null);
    setSelectedCameraId(null);
  };
  const activeRoute = useMemo(
    () => routes.find((route) => route.id === selected),
    [routes, selected],
  );
  const previewRoute = useMemo(
    () => routes.find((route) => route.id === previewRouteId) ?? activeRoute,
    [activeRoute, previewRouteId, routes],
  );
  const selectedIncident = useMemo(
    () => incidents.find((incident) => incident.id === selectedIncidentId),
    [incidents, selectedIncidentId],
  );

  useEffect(() => {
    onSelectRouteRef.current = onSelectRoute;
  }, [onSelectRoute]);

  useEffect(() => {
    if (selectedIncidentId && !selectedIncident) setSelectedIncidentId(null);
  }, [selectedIncident, selectedIncidentId]);

  useEffect(() => {
    if (!container.current || map.current) return;
    let cancelled = false;
    const fallbackTimer = window.setTimeout(() => {
      if (!cancelled) setStatus((current) => current === "loading" ? "failed" : current);
    }, 8_000);

    void import("maplibre-gl")
      .then((maplibregl) => {
        if (cancelled || !container.current) return;
        const instance = new maplibregl.Map({
          container: container.current,
          style: OPEN_STYLE,
          center: [18.477, -33.95],
          zoom: 11.2,
          attributionControl: false,
        });
        instance.addControl(new maplibregl.NavigationControl({ showCompass: false }), "top-right");
        instance.addControl(new maplibregl.AttributionControl({ compact: true }));
        instance.once("load", () => {
          if (cancelled) return;
          window.clearTimeout(fallbackTimer);
          instance.addSource(CELL_SOURCE, { type: "geojson", data: { type: "FeatureCollection", features: [] } });
          instance.addLayer({
            id: CELL_LAYER, type: "fill", source: CELL_SOURCE,
            paint: {
              "fill-color": ["step", ["get", "incident_count"], "#bad6c7", 3, "#d7b866", 6, "#ae454b"],
              "fill-opacity": 0.45,
            },
          });
          instance.addLayer({
            id: CELL_OUTLINE, type: "line", source: CELL_SOURCE,
            paint: { "line-color": "#48534f", "line-width": 1, "line-opacity": 0.65 },
          });
          instance.on("click", CELL_LAYER, (event) => {
            const cellId = event.features?.[0]?.properties?.cell_id;
            if (typeof cellId === "string") { setSelectedCellId(cellId); setSelectedIncidentId(null); clearHazardSelections(); }
          });
          instance.on("mouseenter", CELL_LAYER, () => { instance.getCanvas().style.cursor = "pointer"; });
          instance.on("mouseleave", CELL_LAYER, () => { instance.getCanvas().style.cursor = ""; });
          instance.addSource(WILDFIRE_SOURCE, { type: "geojson", data: EMPTY_FEATURE_COLLECTION });
          instance.addLayer({
            id: WILDFIRE_LAYER, type: "circle", source: WILDFIRE_SOURCE,
            paint: { "circle-color": "#c9432b", "circle-radius": 6, "circle-stroke-width": 1.5, "circle-stroke-color": "#fff", "circle-opacity": 0.9 },
          });
          instance.on("click", WILDFIRE_LAYER, (event) => {
            const index = event.features?.[0]?.properties?.index;
            if (typeof index === "number") { setSelectedWildfireIndex(index); setSelectedWeatherId(null); setSelectedCameraId(null); setSelectedIncidentId(null); setSelectedCellId(null); }
          });
          instance.on("mouseenter", WILDFIRE_LAYER, () => { instance.getCanvas().style.cursor = "pointer"; });
          instance.on("mouseleave", WILDFIRE_LAYER, () => { instance.getCanvas().style.cursor = ""; });
          instance.addSource(WEATHER_SOURCE, { type: "geojson", data: EMPTY_FEATURE_COLLECTION });
          instance.addLayer({
            id: WEATHER_LAYER, type: "circle", source: WEATHER_SOURCE,
            paint: {
              "circle-color": ["match", ["get", "category"],
                "floods", "#2f6fb3",
                "landslides", "#8a5a2e",
                "severeStorms", "#5b4b9e",
                "dustHaze", "#b3a369",
                "snow", "#6fb3d2",
                "tempExtremes", "#c9432b",
                "#5b6b63"],
              "circle-radius": 6, "circle-stroke-width": 1.5, "circle-stroke-color": "#fff", "circle-opacity": 0.9,
            },
          });
          instance.on("click", WEATHER_LAYER, (event) => {
            const id = event.features?.[0]?.properties?.id;
            if (typeof id === "string") { setSelectedWeatherId(id); setSelectedWildfireIndex(null); setSelectedCameraId(null); setSelectedIncidentId(null); setSelectedCellId(null); }
          });
          instance.on("mouseenter", WEATHER_LAYER, () => { instance.getCanvas().style.cursor = "pointer"; });
          instance.on("mouseleave", WEATHER_LAYER, () => { instance.getCanvas().style.cursor = ""; });
          instance.addSource(CAMERA_SOURCE, { type: "geojson", data: EMPTY_FEATURE_COLLECTION });
          instance.addLayer({
            id: CAMERA_LAYER, type: "circle", source: CAMERA_SOURCE,
            paint: { "circle-color": "#2b6cb0", "circle-radius": 5, "circle-stroke-width": 1.5, "circle-stroke-color": "#fff", "circle-opacity": 0.9 },
          });
          instance.on("click", CAMERA_LAYER, (event) => {
            const id = event.features?.[0]?.properties?.id;
            if (typeof id === "string") { setSelectedCameraId(id); setSelectedWildfireIndex(null); setSelectedWeatherId(null); setSelectedIncidentId(null); setSelectedCellId(null); }
          });
          instance.on("mouseenter", CAMERA_LAYER, () => { instance.getCanvas().style.cursor = "pointer"; });
          instance.on("mouseleave", CAMERA_LAYER, () => { instance.getCanvas().style.cursor = ""; });
          instance.addSource(ROUTE_SOURCE, {
            type: "geojson",
            data: routeFeatures(routes, selected, Boolean(telemetry)),
          });
          instance.addLayer({
            id: ROUTE_HIT_LAYER,
            type: "line",
            source: ROUTE_SOURCE,
            layout: { "line-cap": "round", "line-join": "round" },
            paint: { "line-color": "#000000", "line-width": 20, "line-opacity": 0 },
          });
          instance.addLayer({
            id: ROUTE_LAYER,
            type: "line",
            source: ROUTE_SOURCE,
            layout: { "line-cap": "round", "line-join": "round" },
            paint: {
              "line-color": ["get", "colour"],
              "line-width": ["get", "width"],
              "line-opacity": ["get", "opacity"],
            },
          });
          instance.on("mousemove", ROUTE_HIT_LAYER, (event) => {
            instance.getCanvas().style.cursor = "pointer";
            const routeId = event.features?.[0]?.properties?.routeId;
            setPreviewRouteId(typeof routeId === "string" ? routeId : null);
          });
          instance.on("mouseleave", ROUTE_HIT_LAYER, () => {
            instance.getCanvas().style.cursor = "";
            setPreviewRouteId(null);
          });
          instance.on("click", ROUTE_HIT_LAYER, (event) => {
            const routeId = event.features?.[0]?.properties?.routeId;
            if (typeof routeId === "string") onSelectRouteRef.current?.(routeId);
          });
          setStatus("ready");
        });
        instance.on("error", (event) => {
          if (!instance.loaded() && event.error) setStatus("failed");
        });
        map.current = instance;
      })
      .catch(() => {
        if (!cancelled) setStatus("failed");
      });

    return () => {
      cancelled = true;
      window.clearTimeout(fallbackTimer);
      driverMarker.current?.remove();
      incidentMarkers.current.forEach((marker) => marker.remove());
      endpointMarkers.current.forEach((marker) => marker.remove());
      map.current?.remove();
      map.current = null;
    };
  }, []);

  useEffect(() => {
    if (status !== "ready" || !map.current) return;
    (map.current.getSource(CELL_SOURCE) as GeoJSONSource | undefined)?.setData(
      showCells && cells?.data ? cells.data : { type: "FeatureCollection", features: [] },
    );
  }, [cells?.data, showCells, status]);

  useEffect(() => {
    if (status !== "ready" || !map.current) return;
    (map.current.getSource(WILDFIRE_SOURCE) as GeoJSONSource | undefined)?.setData(
      showWildfires && hazards ? wildfireFeatures(hazards.wildfires.data) : EMPTY_FEATURE_COLLECTION,
    );
  }, [hazards?.wildfires.data, showWildfires, status]);

  useEffect(() => {
    if (status !== "ready" || !map.current) return;
    (map.current.getSource(WEATHER_SOURCE) as GeoJSONSource | undefined)?.setData(
      showSevereWeather && hazards ? severeWeatherFeatures(hazards.severeWeather.data) : EMPTY_FEATURE_COLLECTION,
    );
  }, [hazards?.severeWeather.data, showSevereWeather, status]);

  useEffect(() => {
    if (status !== "ready" || !map.current) return;
    (map.current.getSource(CAMERA_SOURCE) as GeoJSONSource | undefined)?.setData(
      showCameras && hazards ? cameraFeatures(hazards.cameras.data) : EMPTY_FEATURE_COLLECTION,
    );
  }, [hazards?.cameras.data, showCameras, status]);

  useEffect(() => {
    if (!container.current) return;
    const observer = new ResizeObserver(() => map.current?.resize());
    observer.observe(container.current);
    return () => observer.disconnect();
  }, []);

  // Expanded map and the full-screen camera both behave like lightboxes: Escape
  // closes them and the page behind must not scroll. The camera sits on top of
  // the map, so it unwinds first. The ResizeObserver above re-fits MapLibre.
  useEffect(() => {
    if (!expanded && !cameraExpanded) return;
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key !== "Escape") return;
      if (cameraExpanded) setCameraExpanded(false);
      else setExpanded(false);
    };
    window.addEventListener("keydown", onKeyDown);
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      window.removeEventListener("keydown", onKeyDown);
      document.body.style.overflow = previousOverflow;
    };
  }, [expanded, cameraExpanded]);

  // Deselecting the camera (or hiding the layer) must not leave the viewer open.
  useEffect(() => {
    if (cameraExpanded && (!selectedCamera || !showCameras)) setCameraExpanded(false);
  }, [cameraExpanded, selectedCamera, showCameras]);

  useEffect(() => {
    const instance = map.current;
    if (!instance) return;
    const update = () => {
      (instance.getSource(ROUTE_SOURCE) as GeoJSONSource | undefined)?.setData(
        routeFeatures(routes, selected, Boolean(telemetry)),
      );
      const points = routes.flatMap((route) => route.geometry);
      if (points.length) {
        const west = Math.min(...points.map((point) => point.longitude));
        const east = Math.max(...points.map((point) => point.longitude));
        const south = Math.min(...points.map((point) => point.latitude));
        const north = Math.max(...points.map((point) => point.latitude));
        instance.fitBounds([[west, south], [east, north]], { padding: 55, duration: window.matchMedia("(prefers-reduced-motion: reduce)").matches ? 0 : 450 });
      }
    };
    if (instance.loaded()) update();
    else instance.once("load", update);
  }, [routes, selected, telemetry?.fitKey]);

  useEffect(() => {
    incidentMarkers.current.forEach((marker) => marker.remove());
    endpointMarkers.current.forEach((marker) => marker.remove());
    incidentMarkers.current = [];
    endpointMarkers.current = [];
    const instance = map.current;
    if (!instance || status !== "ready") return;
    let cancelled = false;
    void import("maplibre-gl").then((maplibregl) => {
      if (cancelled) return;
      const start = activeRoute?.geometry[0];
      const end = activeRoute?.geometry.at(-1);
      for (const [label, point] of [["A", start], ["B", end]] as const) {
        if (!point) continue;
        const element = document.createElement("div");
        element.className = `route-endpoint ${label === "B" ? "destination" : "origin"}`;
        element.textContent = label;
        element.setAttribute("role", "img");
        element.setAttribute("aria-label", label === "A" ? "Route origin" : "Route destination");
        endpointMarkers.current.push(
          new maplibregl.Marker({ element }).setLngLat([point.longitude, point.latitude]).addTo(instance),
        );
      }
      for (const incident of incidents.filter((item) => item.status === "active")) {
        const element = document.createElement("button");
        element.type = "button";
        element.className = `incident-marker severity-${incident.severity}`;
        element.textContent = "!";
        element.setAttribute("aria-label", incidentLabel(incident));
        element.addEventListener("click", (event) => {
          event.stopPropagation();
          setSelectedIncidentId(incident.id);
          setSelectedCellId(null);
          clearHazardSelections();
        });
        incidentMarkers.current.push(
          new maplibregl.Marker({ element })
            .setLngLat([incident.location.longitude, incident.location.latitude])
            .addTo(instance),
        );
      }
    });
    return () => {
      cancelled = true;
      incidentMarkers.current.forEach((marker) => marker.remove());
      endpointMarkers.current.forEach((marker) => marker.remove());
      incidentMarkers.current = [];
      endpointMarkers.current = [];
    };
  }, [activeRoute, incidents, status]);

  useEffect(() => {
    const instance = map.current;
    const point = pointAtProgress(activeRoute, progress);
    if (!instance || !point || status !== "ready" || telemetry) return;
    void import("maplibre-gl").then((maplibregl) => {
      if (!driverMarker.current) {
        const element = document.createElement("div");
        element.className = "driver-marker";
        element.setAttribute("role", "img");
        element.setAttribute("aria-label", "Simulated driver position");
        driverMarker.current = new maplibregl.Marker({ element }).setLngLat(point).addTo(instance);
      } else driverMarker.current.setLngLat(point);
    });
  }, [activeRoute, progress, status, Boolean(telemetry)]);

  return (
    <div className={`map-frame${expanded ? " is-expanded" : ""}`}>
      {cells && (
        <div className="map-layer-toolbar">
          <button type="button" aria-pressed={showCells} onClick={() => { setShowCells(!showCells); setSelectedCellId(null); }}>
            Incident areas {showCells ? "on" : "off"}
          </button>
          <span aria-live="polite">
            {cells.status === "loading" ? "Loading area counts…" : cells.status === "unavailable"
              ? "Area counts unavailable · connect the service to load reports"
              : `${cells.data?.metadata.incident_count ?? 0} reports across ${cells.data?.metadata.cell_count ?? 0} areas`}
          </span>
        </div>
      )}
      {hazards && (
        <div className="map-layer-toolbar hazard-layer-toolbar">
          <button type="button" aria-pressed={showWildfires} onClick={() => { setShowWildfires(!showWildfires); setSelectedWildfireIndex(null); }}>
            Wildfires {showWildfires ? "on" : "off"}
          </button>
          <button type="button" aria-pressed={showSevereWeather} onClick={() => { setShowSevereWeather(!showSevereWeather); setSelectedWeatherId(null); }}>
            Severe weather {showSevereWeather ? "on" : "off"}
          </button>
          <button type="button" aria-pressed={showCameras} onClick={() => { setShowCameras(!showCameras); setSelectedCameraId(null); }}>
            Traffic cameras {showCameras ? "on" : "off"}
          </button>
          <span aria-live="polite">
            {[hazards.wildfires.status, hazards.severeWeather.status, hazards.cameras.status].includes("loading")
              ? "Loading hazard layers…"
              : `${hazards.wildfires.data.length} wildfire hotspots · ${hazards.severeWeather.data.length} severe weather events · ${hazards.cameras.data.length} traffic cameras`}
          </span>
        </div>
      )}
    <div className={`map${telemetry ? " telemetry-map" : ""}`} role="group" aria-label={telemetry ? "Demo vehicle and street sensor map" : "Cape Town route-risk map"} aria-describedby={summaryId}>
      <p className="sr-only" id={summaryId}>
        {telemetry ? "Synthetic vehicle positions and street sensor stations. Select a tracker or station to inspect its readings. No physical devices are connected."
          : activeRoute
          ? `${activeRoute.name} is selected: ${activeRoute.distanceKm} kilometres, ${activeRoute.durationMinutes} minutes, safety estimate ${activeRoute.safetyScore} out of 100. Route lines can be selected to compare alternatives.${weatherStatus === "ready" && weather ? ` Weather is sampled at the origin, mid-route, and destination; the highest exposure is ${weather.riskLabel.toLowerCase()} near the ${weather.highestRiskAt.toLowerCase()}.` : ""} ${incidents.filter((incident) => incident.status === "active").length} active incidents are shown.${status === "ready" ? " The interactive street map is displayed." : " The offline route overview is displayed while the live map is unavailable."}`
          : "No route is selected."}
      </p>
      <div className={`map-label ${status}`}>
        <span>
          {status === "ready"
            ? "Cape Town · live street map"
            : status === "loading"
              ? "Loading live street map..."
              : "Offline route overview"}
        </span>
        {telemetry ? <strong>Demo GPS + sensor replay</strong> : previewRoute && <strong>{previewRoute.name} · {previewRoute.durationMinutes} min · {previewRoute.safetyScore}/100</strong>}
      </div>
      <button
        type="button"
        className="map-expand"
        aria-expanded={expanded}
        aria-label={expanded ? "Exit full-screen map" : "Expand map to full screen"}
        title={expanded ? "Exit full screen (Esc)" : "Expand map to full screen"}
        onClick={() => setExpanded((current) => !current)}
      >
        <ExpandIcon expanded={expanded} />
      </button>
      {status !== "ready" ? (
        <SchematicFallback
          routes={routes}
          selected={selected}
          progress={progress}
          incidents={incidents}
          onSelectRoute={onSelectRoute}
          onPreviewRoute={setPreviewRouteId}
          onSelectIncident={(id) => { setSelectedIncidentId(id); setSelectedCellId(null); }}
          telemetry={telemetry}
        />
      ) : null}
      <div ref={container} className={`maplibre-canvas ${status === "ready" ? "is-ready" : "is-pending"}`} />
      {selectedIncident && <IncidentDetail incident={selectedIncident} onClose={() => setSelectedIncidentId(null)} />}
      {showWildfires && selectedWildfire && (
        <aside className="map-incident-detail" aria-label="Wildfire hotspot details">
          <header><div><span>Active wildfire</span><strong>{selectedWildfire.confidence} confidence</strong></div>
            <button type="button" onClick={() => setSelectedWildfireIndex(null)} aria-label="Close wildfire details">Close</button>
          </header>
          <dl>
            <div><dt>Fire radiative power</dt><dd>{selectedWildfire.frp} MW</dd></div>
            <div><dt>Detected</dt><dd>{incidentTime(selectedWildfire.acquired_at)}</dd></div>
          </dl>
          <small>Source: NASA FIRMS satellite detections, refreshed roughly every 30 minutes.</small>
        </aside>
      )}
      {showSevereWeather && selectedWeatherEvent && (
        <aside className="map-incident-detail" aria-label="Severe weather event details">
          <header><div><span>{SEVERE_WEATHER_LABELS[selectedWeatherEvent.category]}</span><strong>{selectedWeatherEvent.title}</strong></div>
            <button type="button" onClick={() => setSelectedWeatherId(null)} aria-label="Close severe weather details">Close</button>
          </header>
          <small>Source: NASA EONET open events feed.</small>
        </aside>
      )}
      {showCameras && selectedCamera && (
        <aside className="map-incident-detail camera-detail" aria-label="Traffic camera details">
          <header><div><span>Traffic camera</span><strong>{selectedCamera.name}</strong></div>
            <button type="button" onClick={() => setSelectedCameraId(null)} aria-label="Close camera details">Close</button>
          </header>
          {selectedCamera.feed_type === "image" ? (
            <button
              type="button"
              className="camera-feed-button"
              onClick={() => setCameraExpanded(true)}
              aria-label={`View ${selectedCamera.name} full screen`}
            >
              <img
                className="camera-feed-image"
                src={cameraFrameUrl(selectedCamera.feed_url, cameraFrame)}
                alt={`Live still from ${selectedCamera.name}`}
              />
              <span className="camera-feed-hint"><ExpandIcon expanded={false} />Full screen</span>
            </button>
          ) : (
            <p>Live video feed available via the source provider.</p>
          )}
          <small>Source: {selectedCamera.source || "opencctv.org"} public traffic camera network.</small>
        </aside>
      )}
      {showCells && selectedCell && (
        <aside className="map-incident-detail" aria-label="Incident area details">
          <header><div><span>Incident area</span><strong>{selectedCell.properties.incident_count} active reports</strong></div>
            <button type="button" onClick={() => setSelectedCellId(null)} aria-label="Close area details">Close</button>
          </header>
          <p>{cellProvenance(selectedCell.properties.provenance)}</p>
          <dl>
            <div><dt>Highest severity</dt><dd>{selectedCell.properties.max_severity}/5</dd></div>
            <div><dt>Average confidence</dt><dd>{Math.round(selectedCell.properties.average_confidence * 100)}%</dd></div>
            <div><dt>Latest report</dt><dd>{incidentTime(selectedCell.properties.latest_occurred_at)}</dd></div>
          </dl>
          <small>Area counts show report density, not the probability of harm.</small>
        </aside>
      )}
      {!telemetry && <WeatherReadout weather={weather} status={weatherStatus} />}
      <div className="legend" aria-label="Map legend">
        {telemetry ? <>
          <span><i className="telemetry-key vehicle" />Demo vehicle</span>
          <span><i className="telemetry-key sensor" />Demo sensor</span>
          <span><i className="telemetry-key offline" />Offline / stale</span>
          <small>Illustrative positions · not live device data</small>
        </> : <>
        <span><i className="dot green" />Low risk</span>
        <span><i className="dot amber" />Medium</span>
        <span><i className="dot red" />High</span>
        <span><i className="incident-key">!</i>Incident</span>
        {hazards && (
          <>
            <span><i className="dot wildfire" />Wildfire</span>
            <span><i className="dot weather-event" />Severe weather</span>
            <span><i className="dot camera" />Traffic camera</span>
          </>
        )}
        <small>Tap a route line to compare</small>
        </>}
      </div>
    </div>
      {showCells && cells?.data && (
        <div className="map-cell-summary">
          <p>{cellProvenance(cells.data.metadata.provenance)} · active, unexpired reports only. Counts are not safety scores.</p>
          <div className="cell-legend" aria-label="Incident area count legend">
            <span><i className="cell-key few" />1–2 reports</span><span><i className="cell-key some" />3–5 reports</span><span><i className="cell-key many" />6+ reports</span>
          </div>
          {status !== "ready" && <p>The street map is unavailable. Area counts are still listed below.</p>}
          {cells.data.features.length === 0 ? <p>No active incident areas to display.</p> : (
            <details><summary>Review {cells.data.metadata.cell_count} areas</summary>
              <ul className="cell-area-list">{cells.data.features.map((cell, index) => (
                <li key={cell.id}><button type="button" aria-pressed={selectedCellId === cell.id}
                  onClick={() => {
                    setSelectedCellId(cell.id); setSelectedIncidentId(null); clearHazardSelections();
                    const ring = cell.geometry.coordinates[0];
                    if (status === "ready" && ring.length) map.current?.fitBounds([
                      [Math.min(...ring.map((p) => p[0])), Math.min(...ring.map((p) => p[1]))],
                      [Math.max(...ring.map((p) => p[0])), Math.max(...ring.map((p) => p[1]))],
                    ], { padding: 65, maxZoom: 13, duration: 300 });
                  }}>Area {index + 1} · {cell.properties.incident_count} reports · severity up to {cell.properties.max_severity}/5</button></li>
              ))}</ul>
            </details>
          )}
        </div>
      )}
      {cameraExpanded && selectedCamera && selectedCamera.feed_type === "image" && (
        <div
          className="camera-viewer"
          role="dialog"
          aria-modal="true"
          aria-label={`${selectedCamera.name} full screen`}
          onClick={() => setCameraExpanded(false)}
        >
          <div className="camera-viewer-inner" onClick={(event) => event.stopPropagation()}>
            <header>
              <div>
                <span>Traffic camera</span>
                <strong>{selectedCamera.name}</strong>
              </div>
              <div className="camera-viewer-actions">
                <button type="button" onClick={() => setCameraFrame((frame) => frame + 1)}>
                  Refresh
                </button>
                <button type="button" onClick={() => setCameraExpanded(false)} aria-label="Close full-screen camera">
                  Close
                </button>
              </div>
            </header>
            <img
              src={cameraFrameUrl(selectedCamera.feed_url, cameraFrame)}
              alt={`Live still from ${selectedCamera.name}`}
            />
            <small>
              Source: {selectedCamera.source || "opencctv.org"} public traffic camera network ·
              low-resolution stills refreshed on demand, not continuous video · press Escape to close
            </small>
          </div>
        </div>
      )}
    </div>
  );
}
