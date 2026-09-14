import type { Coordinate } from "@roadsignal/types";
import { demoRouteGeometry } from "./demo-route-geometry";

// Synthetic, deterministic replay only. Never forward these values to risk scoring,
// incident verification, the real weather feed, or a production tracking service.
export type TrackerState = "moving" | "idle" | "offline" | "arrived";
export type VehicleReading = {
  id: string; label: string; driver: string; routeId: string; position: Coordinate;
  heading: number; speedKmh: number | null; progress: number; state: TrackerState;
  ageSeconds: number; battery: number | null; accuracyMetres: number | null;
  source: "demo";
};
export type SensorReading = {
  id: string; name: string; position: Coordinate; state: "reporting" | "stale";
  airC: number | null; surfaceC: number | null; rainMmH: number | null; visibilityM: number | null;
  vehiclesPerMinute: number | null; averageSpeedKmh: number | null; ageSeconds: number;
  source: "demo";
};

export const REPLAY_SECONDS = 180;

function distanceMetres(a: Coordinate, b: Coordinate) {
  const radians = Math.PI / 180;
  const dLat = (b.latitude - a.latitude) * radians;
  const dLon = (b.longitude - a.longitude) * radians;
  const h = Math.sin(dLat / 2) ** 2 + Math.cos(a.latitude * radians) * Math.cos(b.latitude * radians) * Math.sin(dLon / 2) ** 2;
  return 6_371_000 * 2 * Math.atan2(Math.sqrt(h), Math.sqrt(Math.max(0, 1 - h)));
}

export function alongPath(points: readonly Coordinate[], progress: number) {
  if (!points.length) throw new Error("A replay path needs at least one point");
  if (!Number.isFinite(progress)) throw new Error("Replay progress must be finite");
  if (progress >= 1) return { position: { ...points[points.length - 1] }, heading: 0 };
  const lengths = points.slice(1).map((point, index) => distanceMetres(points[index], point));
  const total = lengths.reduce((sum, length) => sum + length, 0);
  let remaining = total * Math.max(0, Math.min(1, progress));
  for (let index = 0; index < lengths.length; index++) {
    const length = lengths[index];
    if (!length) continue;
    if (remaining <= length || index === lengths.length - 1) {
      const a = points[index], b = points[index + 1];
      const ratio = Math.max(0, Math.min(1, remaining / length));
      const radians = Math.PI / 180;
      const heading = (Math.atan2(Math.sin((b.longitude - a.longitude) * radians) * Math.cos(b.latitude * radians),
        Math.cos(a.latitude * radians) * Math.sin(b.latitude * radians) - Math.sin(a.latitude * radians) * Math.cos(b.latitude * radians) * Math.cos((b.longitude - a.longitude) * radians)) / radians + 360) % 360;
      return { position: { latitude: a.latitude + (b.latitude - a.latitude) * ratio, longitude: a.longitude + (b.longitude - a.longitude) * ratio }, heading };
    }
    remaining -= length;
  }
  return { position: { ...points[0] }, heading: 0 };
}

export function replaySnapshot(seconds: number): { vehicles: VehicleReading[]; sensors: SensorReading[] } {
  const time = Number.isFinite(seconds) ? Math.max(0, Math.min(REPLAY_SECONDS, seconds)) : 0;
  const moving = [
    { id: "CA 482-771", label: "V1", driver: "Amina Daniels", routeId: "route-balanced" as const, offset: 0.26, speed: 58 },
    { id: "CA 193-044", label: "V2", driver: "Lwazi Mbeki", routeId: "route-fastest" as const, offset: 0.43, speed: 34 },
  ].map((vehicle, index): VehicleReading => {
    // Accelerated corridor replay, not a physics simulation or actual trip ETA.
    const progress = Math.min(1, vehicle.offset + time / REPLAY_SECONDS * (1 - vehicle.offset));
    const arrived = progress === 1;
    return { ...vehicle, ...alongPath(demoRouteGeometry[vehicle.routeId], progress), progress: progress * 100,
      speedKmh: arrived ? 0 : Math.round(vehicle.speed + 4 * Math.sin(time / 11 + index)), state: arrived ? "arrived" : "moving",
      ageSeconds: Math.floor(time) % 3, battery: 91 - index * 14, accuracyMetres: 5 + index * 3, source: "demo" };
  });
  const vehicles: VehicleReading[] = [...moving,
    { id: "CY 827-519", label: "V3", driver: "Nadia Jacobs", routeId: "", position: { latitude: -33.925, longitude: 18.433 }, heading: 0,
      speedKmh: 0, progress: 0, state: "idle", ageSeconds: Math.floor(time) % 5, battery: 84, accuracyMetres: 7, source: "demo" },
    { id: "CA 614-208", label: "V4", driver: "Ethan Williams", routeId: "", position: { latitude: -33.9406, longitude: 18.5047 }, heading: 0,
      speedKmh: null, progress: 0, state: "offline", ageSeconds: 28 * 60 + Math.floor(time), battery: 18, accuracyMetres: null, source: "demo" },
  ];
  const sensors: SensorReading[] = [
    { id: "S1", name: "Woodstock station", position: { latitude: -33.9337, longitude: 18.4477 }, state: "reporting", airC: 17.8, surfaceC: 21.4, rainMmH: 0.2, visibilityM: 8100, vehiclesPerMinute: 24, averageSpeedKmh: 46, ageSeconds: 0, source: "demo" },
    { id: "S2", name: "Athlone station", position: { latitude: -33.9585, longitude: 18.521 }, state: "reporting", airC: 16.2, surfaceC: 18.1, rainMmH: 1.6, visibilityM: 3600, vehiclesPerMinute: 43, averageSpeedKmh: 29, ageSeconds: 0, source: "demo" },
    { id: "S3", name: "Airport approach station", position: { latitude: -33.967, longitude: 18.59 }, state: "stale", airC: 18.1, surfaceC: 23.7, rainMmH: 0, visibilityM: 9500, vehiclesPerMinute: 18, averageSpeedKmh: 61, ageSeconds: 12 * 60 + Math.floor(time), source: "demo" },
  ].map((station, index) => {
    if (station.state === "stale") return station as SensorReading;
    const wave = Math.sin(Math.floor(time / 5) / 5 + index) * 0.4;
    return { ...station, state: "reporting", airC: Math.round((station.airC + wave) * 10) / 10,
      surfaceC: Math.round((station.surfaceC + wave) * 10) / 10,
      vehiclesPerMinute: station.vehiclesPerMinute + Math.round(wave * 7),
      averageSpeedKmh: station.averageSpeedKmh - Math.round(wave * 5), ageSeconds: Math.floor(time) % 5 } as SensorReading;
  });
  return { vehicles, sensors };
}

export function ageLabel(seconds: number) {
  return seconds < 60 ? `${Math.floor(seconds)} s ago` : `${Math.floor(seconds / 60)} min ago`;
}
