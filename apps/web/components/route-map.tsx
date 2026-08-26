"use client";

import type { RouteOption } from "@roadsignal/types";
import type { GeoJSONSource, Map as MapLibreMap, Marker } from "maplibre-gl";
import { useEffect, useId, useMemo, useRef, useState } from "react";

const OPEN_STYLE = "https://tiles.openfreemap.org/styles/liberty";
const ROUTE_SOURCE = "roadsignal-routes";
const ROUTE_LAYER = "roadsignal-route-lines";

type Props = { routes: RouteOption[]; selected: string; progress?: number };

function riskColour(score: number) {
  return score >= 80 ? "#178652" : score >= 60 ? "#c47a0c" : "#c33d3d";
}

function routeFeatures(routes: RouteOption[], selected: string) {
  return {
    type: "FeatureCollection" as const,
    features: routes.flatMap((route) =>
      route.geometry.slice(0, -1).map((point, index) => {
        const next = route.geometry[index + 1];
        const segmentScore = Math.max(
          25,
          route.safetyScore - (index === 1 ? 18 : index % 2 === 0 ? 2 : 8),
        );
        return {
          type: "Feature" as const,
          properties: {
            colour:
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

function SchematicFallback({ routes, selected, progress = 0 }: Props) {
  const colours: Record<string, string> = {
    "route-balanced": "#d4b600",
    "route-safest": "#1f9d61",
    "route-fastest": "#d45545",
  };
  const points = (route: RouteOption) =>
    route.geometry
      .map(
        (_, index) =>
          `${60 + index * 140},${235 - (index % 2) * 65 - (route.id === "route-safest" ? 35 : 0) + (route.id === "route-fastest" ? 28 : 0)}`,
      )
      .join(" ");

  return (
    <svg
      viewBox="0 0 520 300"
      role="img"
      aria-label="Offline schematic route map"
    >
      <path d="M0 65 Q95 92 135 42 T280 70 T520 38V300H0Z" fill="#dceaf3" />
      <g stroke="#c7ced4" strokeWidth="6" fill="none">
        <path d="M20 260L500 48" />
        <path d="M40 75L470 270" />
        <path d="M110 10L300 300" />
      </g>
      {routes.map((route) => (
        <polyline
          key={route.id}
          points={points(route)}
          fill="none"
          stroke={colours[route.id]}
          strokeWidth={selected === route.id ? 9 : 4}
          opacity={selected === route.id ? 1 : 0.35}
          strokeLinecap="round"
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
        fill="#ffda00"
        stroke="#20211d"
        strokeWidth="4"
      />
    </svg>
  );
}

export function RouteMap({ routes, selected, progress = 0 }: Props) {
  const summaryId = useId();
  const container = useRef<HTMLDivElement>(null);
  const map = useRef<MapLibreMap | null>(null);
  const driverMarker = useRef<Marker | null>(null);
  const [failed, setFailed] = useState(false);
  const activeRoute = useMemo(
    () => routes.find((route) => route.id === selected),
    [routes, selected],
  );

  useEffect(() => {
    if (!container.current || map.current) return;
    let cancelled = false;

    void import("maplibre-gl").then(({ default: maplibregl }) => {
      if (cancelled || !container.current) return;
      const instance = new maplibregl.Map({
        container: container.current,
        style: OPEN_STYLE,
        center: [18.477, -33.95],
        zoom: 11.2,
        attributionControl: false,
      });
      instance.addControl(
        new maplibregl.NavigationControl({ showCompass: false }),
        "top-right",
      );
      instance.addControl(new maplibregl.AttributionControl({ compact: true }));
      instance.once("load", () => {
        instance.addSource(ROUTE_SOURCE, {
          type: "geojson",
          data: routeFeatures(routes, selected),
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
      });
      instance.on("error", (event) => {
        if (!instance.loaded() && event.error) setFailed(true);
      });
      map.current = instance;
    });

    return () => {
      cancelled = true;
      driverMarker.current?.remove();
      map.current?.remove();
      map.current = null;
    };
  }, []);

  useEffect(() => {
    if (!container.current) return;
    // MapLibre's own resize watcher can miss layout changes driven by CSS
    // Grid stretch (e.g. the planner's map column growing to match the
    // controls column), leaving stale canvas dimensions and dead space.
    const observer = new ResizeObserver(() => map.current?.resize());
    observer.observe(container.current);
    return () => observer.disconnect();
  }, []);

  useEffect(() => {
    const instance = map.current;
    if (!instance) return;
    const update = () => {
      (instance.getSource(ROUTE_SOURCE) as GeoJSONSource | undefined)?.setData(
        routeFeatures(routes, selected),
      );
      const points = routes.flatMap((route) => route.geometry);
      if (points.length) {
        const west = Math.min(...points.map((point) => point.longitude));
        const east = Math.max(...points.map((point) => point.longitude));
        const south = Math.min(...points.map((point) => point.latitude));
        const north = Math.max(...points.map((point) => point.latitude));
        instance.fitBounds(
          [
            [west, south],
            [east, north],
          ],
          { padding: 55, duration: 450 },
        );
      }
    };
    if (instance.loaded()) update();
    else instance.once("load", update);
  }, [routes, selected]);

  useEffect(() => {
    const instance = map.current;
    const point = pointAtProgress(activeRoute, progress);
    if (!instance || !point) return;
    void import("maplibre-gl").then(({ default: maplibregl }) => {
      if (!driverMarker.current) {
        const element = document.createElement("div");
        element.className = "driver-marker";
        element.setAttribute("aria-label", "Simulated driver position");
        driverMarker.current = new maplibregl.Marker({ element })
          .setLngLat(point)
          .addTo(instance);
      } else driverMarker.current.setLngLat(point);
    });
  }, [activeRoute, progress]);

  return (
    <div
      className="map"
      role="group"
      aria-label="Cape Town route-risk map"
      aria-describedby={summaryId}
    >
      <p className="sr-only" id={summaryId}>
        {activeRoute
          ? `${activeRoute.name} is selected: ${activeRoute.distanceKm} kilometres, ${activeRoute.durationMinutes} minutes, safety estimate ${activeRoute.safetyScore} out of 100.${failed ? " The offline schematic map is displayed." : " The interactive street map is displayed."}`
          : "No route is selected."}
      </p>
      <div className="map-label">Cape Town - Free OpenStreetMap-based map</div>
      {failed ? (
        <SchematicFallback
          routes={routes}
          selected={selected}
          progress={progress}
        />
      ) : null}
      <div
        ref={container}
        className={failed ? "maplibre-canvas is-hidden" : "maplibre-canvas"}
      />
      <div className="legend">
        <span>
          <i className="dot green" />
          Low-risk segment
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
