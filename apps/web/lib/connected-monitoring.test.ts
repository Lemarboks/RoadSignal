import { describe, expect, it } from "vitest";
import { connectedReadings, evidenceSourceUrl, validateMonitoringSnapshot, type MonitoringSnapshot } from "./connected-monitoring";

function snapshot(): MonitoringSnapshot {
  return { source: "demo", generated_at: "2026-09-12T10:00:00Z", notice: "Synthetic devices", alerts: [],
    automation: { configured: true, last_run_at: null, last_run_key: null, run_count: 0 },
    devices: [
      { id: "CA 482-771", kind: "vehicle", label: "Tracker one", source: "demo", state: "moving", reported_at: "2026-09-12T09:59:58Z", received_at: "2026-09-12T10:00:00Z", latitude: -33.95, longitude: 18.55, age_seconds: 2, is_stale: false, readings: { speedKmh: 44, battery: 80, heading: 90 } },
      { id: "S1", kind: "sensor", label: "Woodstock station", source: "demo", state: "reporting", reported_at: "2026-09-12T10:00:00Z", received_at: "2026-09-12T10:00:00Z", latitude: -33.93, longitude: 18.44, age_seconds: 0, is_stale: false, readings: { airC: 18.2, rainMmH: 0 } },
    ],
  };
}

describe("connected monitoring preserves server provenance", () => {
  it("never fills missing devices or readings from the browser replay", () => {
    expect(connectedReadings(null)).toEqual({ vehicles: [], sensors: [] });
    const { vehicles, sensors } = connectedReadings(validateMonitoringSnapshot(snapshot()));
    expect(vehicles).toHaveLength(1); expect(sensors).toHaveLength(1);
    expect(vehicles[0].position).toEqual({ latitude: -33.95, longitude: 18.55 });
    expect(vehicles[0].speedKmh).toBe(44);
    expect(vehicles[0].accuracyMetres).toBeNull();
    expect(sensors[0].surfaceC).toBeNull(); expect(sensors[0].rainMmH).toBe(0);
  });
  it("retains last accepted positions but marks every device stale after disconnection", () => {
    const { vehicles, sensors } = connectedReadings(snapshot(), 15, true);
    expect(vehicles[0].position.longitude).toBe(18.55);
    expect(vehicles[0].state).toBe("offline"); expect(vehicles[0].speedKmh).toBeNull();
    expect(vehicles[0].ageSeconds).toBe(17);
    expect(sensors[0].state).toBe("stale"); expect(sensors[0].airC).toBe(18.2);
  });
  it("ages devices from server timestamps and respects explicit stale flags", () => {
    const data = snapshot();
    data.devices[0].age_seconds = 0;
    expect(connectedReadings(data, 121).vehicles[0].state).toBe("offline");
    expect(connectedReadings(data, 301).sensors[0].state).toBe("stale");
    data.devices[1].is_stale = true;
    expect(connectedReadings(data).sensors[0].state).toBe("stale");
  });
  it("rejects malformed or mixed-provenance snapshots instead of rendering them", () => {
    expect(() => validateMonitoringSnapshot({ ...snapshot(), source: "real" })).toThrow();
    const data = snapshot(); data.devices[0].latitude = NaN;
    expect(() => validateMonitoringSnapshot(data)).toThrow();
    const repeated = snapshot(); repeated.devices.push(repeated.devices[0]);
    expect(() => validateMonitoringSnapshot(repeated)).toThrow();
  });
  it("does not turn non-finite or missing readings into numeric observations", () => {
    const data = snapshot(); data.devices[0].readings.speedKmh = NaN; data.devices[1].readings.airC = Infinity;
    const result = connectedReadings(data);
    expect(result.vehicles[0].speedKmh).toBeNull(); expect(result.sensors[0].airC).toBeNull();
  });
  it("only makes HTTP(S) evidence source links clickable", () => {
    expect(evidenceSourceUrl("https://example.org/report")).toBe("https://example.org/report");
    expect(evidenceSourceUrl("javascript:alert(1)")).toBeNull();
    expect(evidenceSourceUrl("file:///secret")).toBeNull();
    expect(evidenceSourceUrl(null)).toBeNull();
  });
});
