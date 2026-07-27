import { describe, expect, it } from "vitest";
import { demoRouteGeometry } from "./demo-route-geometry";

describe("bundled demonstration road geometry", () => {
  it("keeps every route detailed and anchored to the same journey", () => {
    for (const geometry of Object.values(demoRouteGeometry)) {
      expect(geometry.length).toBeGreaterThan(90);
      expect(geometry[0].latitude).toBeCloseTo(-33.925, 2);
      expect(geometry[0].longitude).toBeCloseTo(18.424, 2);
      expect(geometry.at(-1)?.latitude).toBeCloseTo(-33.972, 2);
      expect(geometry.at(-1)?.longitude).toBeCloseTo(18.602, 2);
    }
  });

  it("does not contain straight-line jumps across the basemap", () => {
    for (const geometry of Object.values(demoRouteGeometry)) {
      for (let index = 1; index < geometry.length; index += 1) {
        const previous = geometry[index - 1];
        const current = geometry[index];
        const delta = Math.hypot(
          current.latitude - previous.latitude,
          current.longitude - previous.longitude,
        );
        expect(delta).toBeLessThan(0.03);
      }
    }
  });
});
