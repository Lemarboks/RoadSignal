"use client";
import { useEffect, useRef } from "react";
import type { Map as MapLibreMap, Marker } from "maplibre-gl";
import type { SensorReading, VehicleReading } from "../lib/demo-telemetry";

export type MapTelemetry = {
  vehicles: VehicleReading[]; sensors: SensorReading[]; selectedVehicle: string | null; selectedSensor: string | null;
  onSelectVehicle: (id: string) => void; onSelectSensor: (id: string) => void;
  animating: boolean; fitKey: number;
};

export function useTelemetryMarkers(map: React.RefObject<MapLibreMap | null>, ready: boolean, telemetry?: MapTelemetry) {
  const markers = useRef(new Map<string, Marker>());
  useEffect(() => {
    if (!ready || !map.current || !telemetry) return;
    const instance = map.current;
    let cancelled = false, frame = 0;
    const movements: { marker: Marker; from: [number, number]; to: [number, number] }[] = [];
    void import("maplibre-gl").then(({ default: maplibregl }) => {
      if (cancelled) return;
      const visibleIds = new Set<string>();
      for (const reading of [...telemetry.sensors, ...telemetry.vehicles]) {
        const vehicle = "driver" in reading;
        const key = `${vehicle ? "vehicle" : "sensor"}-${reading.id}`;
        visibleIds.add(key);
        const target: [number, number] = [reading.position.longitude, reading.position.latitude];
        let marker = markers.current.get(key);
        if (!marker) {
          const element = document.createElement("button"); element.type = "button";
          const label = document.createElement("span"); element.append(label);
          marker = new maplibregl.Marker({ element }).setLngLat(target).addTo(instance);
          markers.current.set(key, marker);
        }
        const element = marker.getElement();
        const selected = vehicle ? telemetry.selectedVehicle === reading.id : telemetry.selectedSensor === reading.id;
        // MapLibre owns marker/anchor classes (including absolute positioning).
        // Only change our application classes; never replace className.
        element.classList.add("telemetry-marker", vehicle ? "vehicle" : "sensor");
        for (const state of ["moving", "idle", "offline", "arrived", "reporting", "stale"]) {
          element.classList.toggle(state, reading.state === state);
        }
        element.classList.toggle("is-selected", selected);
        element.setAttribute("aria-label", vehicle ? `Demo tracker ${reading.id}, ${reading.state}` : `Demo sensor ${reading.name}, ${reading.state}`);
        element.setAttribute("aria-pressed", String(selected));
        element.firstElementChild!.textContent = vehicle ? reading.label : reading.id;
        element.style.setProperty("--heading", `${vehicle ? reading.heading : 0}deg`);
        element.onclick = (event) => { event.stopPropagation(); vehicle ? telemetry.onSelectVehicle(reading.id) : telemetry.onSelectSensor(reading.id); };
        if (vehicle && telemetry.animating && reading.state === "moving") {
          const point = marker.getLngLat(); movements.push({ marker, from: [point.lng, point.lat], to: target });
        } else marker.setLngLat(target);
      }
      for (const [key, marker] of markers.current) if (!visibleIds.has(key)) { marker.remove(); markers.current.delete(key); }
      const started = performance.now();
      const animate = (now: number) => {
        if (cancelled) return;
        const fraction = Math.min(1, (now - started) / 900);
        movements.forEach(({ marker, from, to }) => marker.setLngLat([from[0] + (to[0] - from[0]) * fraction, from[1] + (to[1] - from[1]) * fraction]));
        if (fraction < 1 && movements.length) frame = requestAnimationFrame(animate);
      };
      if (movements.length) frame = requestAnimationFrame(animate);
    });
    return () => { cancelled = true; cancelAnimationFrame(frame); };
  }, [map, ready, telemetry]);
  useEffect(() => () => { markers.current.forEach((marker) => marker.remove()); markers.current.clear(); }, []);
}
