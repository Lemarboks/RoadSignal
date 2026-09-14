import type { SensorReading, VehicleReading } from "./demo-telemetry";

export type MonitoringDevice = {
  id: string; kind: "vehicle" | "sensor"; label: string; source: "demo";
  state: "moving" | "idle" | "offline" | "arrived" | "reporting" | "stale";
  reported_at: string; received_at: string; latitude: number; longitude: number;
  readings: Record<string, number | null>; age_seconds: number; is_stale: boolean;
};
export type MonitoringSnapshot = {
  source: "demo"; generated_at: string; devices: MonitoringDevice[];
  alerts: { id: string; kind: string; device_id: string; source: "demo"; status: "open" | "resolved"; opened_at: string; resolved_at: string | null; message: string }[];
  automation: { configured: boolean; last_run_at: string | null; last_run_key: string | null; run_count: number };
  notice: string;
};
export type EvidenceItem = {
  id: string; claim: string; source: "demo" | "submitted";
  evidence: { text: string; source_url: string | null; observed_at: string | null }[];
  analysis: Record<string, unknown> | null; status: "pending" | "approved" | "rejected";
  created_at: string; review_note: string | null; decision_scope: "evidence_review_only"; incident_published: false;
};

const vehicleIdentity: Record<string, { label: string; driver: string; routeId: string }> = {
  "CA 482-771": { label: "V1", driver: "Amina Daniels", routeId: "route-balanced" },
  "CA 193-044": { label: "V2", driver: "Lwazi Mbeki", routeId: "route-fastest" },
  "CY 827-519": { label: "V3", driver: "Nadia Jacobs", routeId: "" },
  "CA 614-208": { label: "V4", driver: "Ethan Williams", routeId: "" },
};

export function readingNumber(value: unknown): number | null {
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}

export function validateMonitoringSnapshot(value: unknown): MonitoringSnapshot {
  if (!value || typeof value !== "object") throw new Error("The monitoring service returned an invalid snapshot.");
  const snapshot = value as MonitoringSnapshot;
  if (snapshot.source !== "demo" || !Array.isArray(snapshot.devices) || !Array.isArray(snapshot.alerts)
    || !snapshot.automation || !Number.isFinite(Date.parse(snapshot.generated_at))) {
    throw new Error("The monitoring service returned an invalid snapshot.");
  }
  const ids = new Set<string>();
  for (const device of snapshot.devices) {
    if (!device || device.source !== "demo" || typeof device.id !== "string" || !device.id || ids.has(device.id)
      || !["vehicle", "sensor"].includes(device.kind) || typeof device.label !== "string"
      || readingNumber(device.latitude) === null || Math.abs(device.latitude) > 90
      || readingNumber(device.longitude) === null || Math.abs(device.longitude) > 180
      || !Number.isFinite(Date.parse(device.reported_at)) || !device.readings || typeof device.readings !== "object"
      || readingNumber(device.age_seconds) === null || device.age_seconds < 0 || typeof device.is_stale !== "boolean"
      || !(device.kind === "vehicle" ? ["moving", "idle", "offline", "arrived"] : ["reporting", "stale"]).includes(device.state)) {
      throw new Error("The monitoring service returned invalid device data. Last accepted positions are retained.");
    }
    ids.add(device.id);
  }
  return snapshot;
}

// No local coordinates or replay samples are used here. Clock freshness advances
// from server-reported age, not the browser's potentially skewed wall clock.
export function connectedReadings(snapshot: MonitoringSnapshot | null, elapsedSeconds = 0, connectionLost = false) {
  const vehicles: VehicleReading[] = [], sensors: SensorReading[] = [];
  if (!snapshot) return { vehicles, sensors };
  for (const device of snapshot.devices) {
    const ageSeconds = Math.max(device.age_seconds, (Date.parse(snapshot.generated_at) - Date.parse(device.reported_at)) / 1000)
      + Math.max(0, elapsedSeconds);
    const stale = connectionLost || device.is_stale || ageSeconds > (device.kind === "vehicle" ? 120 : 300);
    const position = { latitude: device.latitude, longitude: device.longitude };
    const number = (key: string) => readingNumber(device.readings[key]);
    if (device.kind === "vehicle") {
      const identity = vehicleIdentity[device.id] ?? { label: device.label, driver: "Demo tracker", routeId: "" };
      vehicles.push({ id: device.id, ...identity, position, source: "demo", ageSeconds,
        state: stale ? "offline" : device.state as VehicleReading["state"], speedKmh: stale || device.state === "offline" ? null : number("speedKmh"),
        heading: number("heading") ?? 0, progress: number("progress") ?? 0, battery: number("battery"), accuracyMetres: number("accuracyMetres"),
      });
    } else sensors.push({ id: device.id, name: device.label, position, source: "demo", ageSeconds,
      state: stale || device.state === "stale" ? "stale" : "reporting", airC: number("airC"), surfaceC: number("surfaceC"),
      rainMmH: number("rainMmH"), visibilityM: number("visibilityM"), vehiclesPerMinute: number("vehiclesPerMinute"), averageSpeedKmh: number("averageSpeedKmh"),
    });
  }
  return { vehicles, sensors };
}

export function evidenceSourceUrl(value: string | null) {
  if (!value) return null;
  try { const url = new URL(value); return ["https:", "http:"].includes(url.protocol) ? url.href : null; }
  catch { return null; }
}

export function timestampLabel(value: string | null) {
  if (!value || !Number.isFinite(Date.parse(value))) return "Not recorded";
  return new Date(value).toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" });
}
