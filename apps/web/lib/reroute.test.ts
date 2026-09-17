import { describe, expect, it } from "vitest";
import type { Incident, RouteOption } from "@roadsignal/types";
import {
  bestAlternative,
  closestIncidentKm,
  routeAvoidsIncidents,
} from "./reroute";

// A short stretch of the N2 corridor and a parallel road well to the south.
const N2 = [
  { latitude: -33.95, longitude: 18.50 },
  { latitude: -33.955, longitude: 18.52 },
  { latitude: -33.96, longitude: 18.54 },
];
const SOUTHERN = [
  { latitude: -34.02, longitude: 18.50 },
  { latitude: -34.025, longitude: 18.52 },
  { latitude: -34.03, longitude: 18.54 },
];

function route(id: string, safetyScore: number, geometry = N2): RouteOption {
  return {
    id,
    name: id,
    distanceKm: 20,
    durationMinutes: 30,
    safetyScore,
    geometry,
  } as RouteOption;
}

function incident(latitude: number, longitude: number, status = "active"): Incident {
  return {
    id: `i-${latitude}-${longitude}`,
    incidentType: "Accident",
    severity: 4,
    confidence: 0.8,
    description: "Collision",
    location: { latitude, longitude },
    status,
  } as Incident;
}

// Sits directly on the N2 geometry, far from the southern road.
const ON_N2 = incident(-33.955, 18.52);

describe("incident proximity", () => {
  it("measures how close a route passes to an active incident", () => {
    expect(closestIncidentKm(route("a", 80), [ON_N2])).toBeLessThan(0.05);
    expect(closestIncidentKm(route("b", 80, SOUTHERN), [ON_N2])).toBeGreaterThan(5);
  });

  it("ignores incidents that are no longer active", () => {
    const resolved = incident(-33.955, 18.52, "resolved");
    expect(closestIncidentKm(route("a", 80), [resolved])).toBe(Infinity);
    expect(routeAvoidsIncidents(route("a", 80), [resolved])).toBe(true);
  });

  it("treats a route with no incidents as clear", () => {
    expect(routeAvoidsIncidents(route("a", 80), [])).toBe(true);
  });
});

describe("bestAlternative", () => {
  it("offers nothing when no alternative is materially safer", () => {
    const routes = [route("current", 80), route("other", 81)];
    expect(bestAlternative(routes, "current", [])).toBeNull();
  });

  it("offers nothing when the only alternative is worse", () => {
    const routes = [route("current", 80), route("worse", 55)];
    expect(bestAlternative(routes, "current", [])).toBeNull();
  });

  it("offers a materially safer alternative", () => {
    const routes = [route("current", 60), route("safer", 78)];
    const suggestion = bestAlternative(routes, "current", []);
    expect(suggestion?.route.id).toBe("safer");
    expect(suggestion?.improvement).toBe(18);
  });

  it("prefers a route that clears the incident over one that merely scores higher", () => {
    // "highScore" is the best on paper but runs straight through the incident;
    // "clear" takes the southern road. The old rule would have picked highScore.
    const routes = [
      route("current", 60),
      route("highScore", 90),
      route("clear", 70, SOUTHERN),
    ];
    const suggestion = bestAlternative(routes, "current", [ON_N2]);
    expect(suggestion?.route.id).toBe("clear");
    expect(suggestion?.avoidsIncidents).toBe(true);
    expect(suggestion?.reason).toContain("clears the reported incident");
  });

  it("offers a clear route even at a similar score when the current route is hit", () => {
    const routes = [route("current", 72), route("clear", 73, SOUTHERN)];
    const suggestion = bestAlternative(routes, "current", [ON_N2]);
    expect(suggestion?.route.id).toBe("clear");
    expect(suggestion?.improvement).toBeLessThan(4); // below the usual threshold
  });

  it("does not offer an alternative that also runs through the incident", () => {
    // Both routes are hit, and the alternative is not materially safer.
    const routes = [route("current", 70), route("alsoHit", 72)];
    expect(bestAlternative(routes, "current", [ON_N2])).toBeNull();
  });

  it("returns null when the selected route is unknown", () => {
    expect(bestAlternative([route("a", 80)], "missing", [])).toBeNull();
  });

  it("explains the suggestion in terms a driver can check", () => {
    const routes = [route("current", 55), route("safer", 80)];
    const suggestion = bestAlternative(routes, "current", []);
    expect(suggestion?.reason).toContain("safer");
    expect(suggestion?.reason).toContain("+25");
  });
});
