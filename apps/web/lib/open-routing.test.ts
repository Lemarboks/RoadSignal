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
