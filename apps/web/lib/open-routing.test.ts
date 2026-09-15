import { afterEach, describe, expect, it, vi } from "vitest";
import {
  analyseOpenRoutes,
  PlaceNotFoundError,
  resolvePlace,
  type ResolvedPlace,
} from "./open-routing";

const origin: ResolvedPlace = {
  displayName: "Cape Town City Centre",
  latitude: -33.9249,
  longitude: 18.4241,
};
const destination: ResolvedPlace = {
  displayName: "Cape Town International Airport",
  latitude: -33.9715,
  longitude: 18.6021,
};

function roadRoute(duration: number, distance: number, latitudeOffset: number) {
  return {
    duration,
    distance,
    geometry: {
      coordinates: [
        [origin.longitude, origin.latitude],
        [18.5, -33.95 + latitudeOffset],
        [destination.longitude, destination.latitude],
      ],
    },
    legs: [{ steps: [{ name: `Test corridor ${latitudeOffset}` }] }],
  };
}

function routeWithSteps() {
  return {
    duration: 1_500,
    distance: 20_000,
    geometry: {
      coordinates: [
        [origin.longitude, origin.latitude],
        [18.5, -33.95],
        [destination.longitude, destination.latitude],
      ],
    },
    legs: [{
      steps: [
        { name: "Long Street", distance: 500, duration: 60, maneuver: { type: "depart", location: [origin.longitude, origin.latitude] } },
        { name: "", ref: "N2", distance: 8000, duration: 420, maneuver: { type: "turn", modifier: "left", location: [18.5, -33.95] } },
        { name: "", distance: 0, duration: 0, maneuver: { type: "arrive", location: [destination.longitude, destination.latitude] } },
      ],
    }],
  };
}

afterEach(() => vi.unstubAllGlobals());

describe("open routing adapter", () => {
  it("uses road-provider duration, distance and geometry for three alternatives", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response(
          JSON.stringify({
            code: "Ok",
            routes: [
              roadRoute(1_500, 20_000, 0),
              roadRoute(1_200, 18_000, 0.02),
              roadRoute(1_700, 22_000, -0.02),
            ],
          }),
          { status: 200 },
        ),
      ),
    );

    const result = await analyseOpenRoutes(
      "origin",
      "destination",
      "fastest",
      [],
      origin,
      destination,
    );

    expect(result.routes).toHaveLength(3);
    expect(result.routes.map((route) => route.distanceKm)).toEqual([
      20, 18, 22,
    ]);
    expect(
      result.routes.find((route) => route.recommended)?.durationMinutes,
    ).toBe(20);
    expect(result.routes.every((route) => route.geometry.length === 3)).toBe(
      true,
    );
  });

  it("extracts turn-by-turn steps from the road provider's maneuvers", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response(
          JSON.stringify({
            code: "Ok",
            routes: [routeWithSteps(), roadRoute(1_200, 18_000, 0.02), roadRoute(1_700, 22_000, -0.02)],
          }),
          { status: 200 },
        ),
      ),
    );

    const result = await analyseOpenRoutes(
      "origin",
      "destination",
      "fastest",
      [],
      origin,
      destination,
    );

    const steps = result.routes[0].steps;
    expect(steps.map((step) => step.maneuver)).toEqual(["depart", "turn-left", "arrive"]);
    expect(steps[1].instruction).toBe("Turn left onto N2");
    expect(steps[1].location).toEqual({ latitude: -33.95, longitude: 18.5 });
    expect(steps[2].instruction).toBe("Arrive at your destination");
  });

  it("reports an unmatched explicit Cape Town search", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(new Response("[]", { status: 200 })),
    );
    await expect(
      resolvePlace("place-that-does-not-exist-123"),
    ).rejects.toBeInstanceOf(PlaceNotFoundError);
  });
});
