import { afterEach, describe, expect, it, vi } from "vitest";
import { applyWeatherRisk, fetchRouteWeather, type RouteWeather } from "./open-weather";
import { demoRouteGeometry } from "./demo-route-geometry";

afterEach(() => vi.unstubAllGlobals());

describe("open weather adapter", () => {
  it("requests weather without credentials and validates the response", async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response(JSON.stringify({
      current: {
        time: "2026-08-11T18:00",
        temperature_2m: 16.2,
        apparent_temperature: 15.1,
        precipitation: 1.2,
        weather_code: 61,
        wind_speed_10m: 42,
        visibility: 4200,
      },
    }), { status: 200 }));
    vi.stubGlobal("fetch", fetchMock);

    const weather = await fetchRouteWeather(
      { latitude: -33.92, longitude: 18.42 },
      { latitude: -33.97, longitude: 18.6 },
    );

    expect(weather.condition).toBe("Rain");
    expect(weather.riskLabel).toBe("Moderate");
    expect(fetchMock.mock.calls[0][1]).toMatchObject({ credentials: "omit", referrerPolicy: "no-referrer" });
    expect(String(fetchMock.mock.calls[0][0])).toContain("latitude=-33.95");
  });

  it("rejects malformed measurements", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(JSON.stringify({
      current: { temperature_2m: "unsafe", apparent_temperature: 15, precipitation: 0, weather_code: 0, wind_speed_10m: 10, visibility: 10000 },
    }), { status: 200 })));
    await expect(fetchRouteWeather(
      { latitude: -33.92, longitude: 18.42 },
      { latitude: -33.97, longitude: 18.6 },
    )).rejects.toThrow("invalid measurements");
  });

  it("applies weather penalties without mutating route input", () => {
    const route = {
      id: "one", name: "One", durationMinutes: 20, distanceKm: 10, safetyScore: 80,
      confidence: 0.8, riskLevel: "low" as const, recommended: true, differenceFromFastest: 0,
      factors: ["Traffic"], breakdown: { crime: 1, accident: 1, traffic: 1, weather: 1, roadCondition: 1, community: 1 },
      explanation: "Test route.", geometry: demoRouteGeometry["route-balanced"],
    };
    const weather: RouteWeather = {
      temperatureC: 15, apparentTemperatureC: 14, precipitationMm: 2, windSpeedKmh: 40,
      visibilityKm: 4, weatherCode: 61, observedAt: "2026-08-11T18:00", condition: "Rain",
      riskLabel: "Moderate", riskPenalty: 7, factors: ["Rain"],
    };
    const adjusted = applyWeatherRisk([route], weather, "balanced");
    expect(adjusted[0].safetyScore).toBe(73);
    expect(adjusted[0].factors).toContain("Rain");
    expect(route.safetyScore).toBe(80);
  });
});
