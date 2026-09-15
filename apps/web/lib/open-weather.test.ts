import { afterEach, describe, expect, it, vi } from "vitest";
import { applyWeatherRisk, fetchRouteWeather, type RouteWeather } from "./open-weather";
import { demoRouteGeometry } from "./demo-route-geometry";

afterEach(() => vi.unstubAllGlobals());

describe("open weather adapter", () => {
  it("samples three route points without credentials and keeps the highest risk", async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response(JSON.stringify([
      {
        current: {
          time: "2026-08-11T18:00",
          temperature_2m: 15,
          apparent_temperature: 14.4,
          precipitation: 0,
          weather_code: 1,
          wind_speed_10m: 12,
          visibility: 10_000,
        },
      },
      {
        current: {
          time: "2026-08-11T18:00",
          temperature_2m: 16.2,
          apparent_temperature: 15.1,
          precipitation: 1.2,
          weather_code: 61,
          wind_speed_10m: 42,
          visibility: 4_200,
        },
      },
      {
        current: {
          time: "2026-08-11T18:00",
          temperature_2m: 17,
          apparent_temperature: 16,
          precipitation: 2,
          weather_code: 95,
          wind_speed_10m: 55,
          visibility: 2_000,
        },
      },
    ]), { status: 200 }));
    vi.stubGlobal("fetch", fetchMock);

    const weather = await fetchRouteWeather(
      { latitude: -33.92, longitude: 18.42 },
      { latitude: -33.97, longitude: 18.6 },
    );

    expect(weather.condition).toBe("Thunderstorm");
    expect(weather.riskLabel).toBe("High");
    expect(weather.samples).toHaveLength(3);
    expect(weather.highestRiskAt).toBe("Destination");
    expect(fetchMock.mock.calls[0][1]).toMatchObject({
      credentials: "omit",
      referrerPolicy: "no-referrer",
    });
    const requestUrl = new URL(String(fetchMock.mock.calls[0][0]));
    expect(requestUrl.searchParams.get("latitude")).toBe("-33.92,-33.95,-33.97");
    expect(requestUrl.searchParams.get("longitude")).toBe("18.42,18.51,18.60");
    expect(requestUrl.searchParams.get("models")).toBe("best_match");
  });

  it("rejects malformed measurements", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(JSON.stringify({
      current: {
        temperature_2m: "unsafe",
        apparent_temperature: 15,
        precipitation: 0,
        weather_code: 0,
        wind_speed_10m: 10,
        visibility: 10_000,
      },
    }), { status: 200 })));
    await expect(fetchRouteWeather(
      { latitude: -33.92, longitude: 18.42 },
      { latitude: -33.97, longitude: 18.6 },
    )).rejects.toThrow("invalid measurements");
  });

  it("applies weather penalties without mutating route input", () => {
    const route = {
      id: "one",
      name: "One",
      durationMinutes: 20,
      distanceKm: 10,
      safetyScore: 80,
      confidence: 0.8,
      riskLevel: "low" as const,
      recommended: true,
      differenceFromFastest: 0,
      factors: ["Traffic"],
      breakdown: {
        crime: 1,
        accident: 1,
        traffic: 1,
        weather: 1,
        roadCondition: 1,
        community: 1,
      },
      explanation: "Test route.",
      geometry: demoRouteGeometry["route-balanced"],
      steps: [],
    };
    const weather: RouteWeather = {
      temperatureC: 15,
      apparentTemperatureC: 14,
      precipitationMm: 2,
      windSpeedKmh: 40,
      visibilityKm: 4,
      weatherCode: 61,
      observedAt: "2026-08-11T18:00",
      condition: "Rain",
      riskLabel: "Moderate",
      riskPenalty: 7,
      factors: ["Rain"],
      highestRiskAt: "Mid-route",
      samples: [{
        label: "Mid-route",
        latitude: -33.95,
        longitude: 18.51,
        temperatureC: 15,
        apparentTemperatureC: 14,
        precipitationMm: 2,
        windSpeedKmh: 40,
        visibilityKm: 4,
        weatherCode: 61,
        observedAt: "2026-08-11T18:00",
        condition: "Rain",
        riskLabel: "Moderate",
        riskPenalty: 7,
        factors: ["Rain"],
      }],
    };
    const adjusted = applyWeatherRisk([route], weather, "balanced");
    expect(adjusted[0].safetyScore).toBe(73);
    expect(adjusted[0].factors).toContain("Rain");
    expect(route.safetyScore).toBe(80);
  });
});
