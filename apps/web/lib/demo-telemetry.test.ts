import { describe, expect, it } from "vitest";
import { alongPath, REPLAY_SECONDS, replaySnapshot } from "./demo-telemetry";

describe("synthetic fleet replay", () => {
  it("interpolates by distance rather than point count", () => {
    const points = [{ latitude: 0, longitude: 0 }, { latitude: 0, longitude: 1 }, { latitude: 0, longitude: 10 }];
    expect(alongPath(points, 0.5).position.longitude).toBeCloseTo(5);
    expect(alongPath(points, -1).position.longitude).toBe(0);
    expect(alongPath(points, 2).position.longitude).toBe(10);
    expect(alongPath(points, 0.5).heading).toBeCloseTo(90);
  });
  it("handles degenerate paths and rejects invalid geometry requests", () => {
    const point = { latitude: -33, longitude: 18 };
    expect(alongPath([point, point], 0.5).position).toEqual(point);
    expect(() => alongPath([], 0)).toThrow();
    expect(() => alongPath([point], NaN)).toThrow();
  });
  it("has reproducible motion, stationary idle/offline units and demo provenance", () => {
    const before = replaySnapshot(0), after = replaySnapshot(30);
    expect(after).toEqual(replaySnapshot(30));
    expect(after.vehicles[0].position).not.toEqual(before.vehicles[0].position);
    expect(after.vehicles[2].position).toEqual(before.vehicles[2].position);
    expect(after.vehicles[3].position).toEqual(before.vehicles[3].position);
    expect(after.vehicles[3].speedKmh).toBeNull();
    expect(after.vehicles[3].ageSeconds).toBeGreaterThan(before.vehicles[3].ageSeconds);
    expect([...after.vehicles, ...after.sensors].every((item) => item.source === "demo")).toBe(true);
  });
  it("freezes stale readings and stops at the end instead of teleporting vehicles", () => {
    const start = replaySnapshot(0), end = replaySnapshot(REPLAY_SECONDS + 100);
    expect(end.vehicles[0].state).toBe("arrived");
    expect(end.vehicles[0].speedKmh).toBe(0);
    expect(end.vehicles[0].progress).toBe(100);
    expect(end.sensors[2].airC).toBe(start.sensors[2].airC);
    expect(end.sensors[2].ageSeconds).toBeGreaterThan(start.sensors[2].ageSeconds);
  });
});
