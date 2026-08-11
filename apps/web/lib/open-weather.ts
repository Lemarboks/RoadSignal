import type { Coordinate, RouteOption, RoutePreference } from "@saferoute/types";

const DEFAULT_WEATHER_URL = "https://api.open-meteo.com/v1/forecast";
const REQUEST_TIMEOUT_MS = 6_500;

export type RouteWeather = {
  temperatureC: number;
  apparentTemperatureC: number;
  precipitationMm: number;
  windSpeedKmh: number;
  visibilityKm: number;
  weatherCode: number;
  observedAt: string;
  condition: string;
  riskLabel: "Low" | "Moderate" | "High";
  riskPenalty: number;
  factors: string[];
};

type OpenMeteoResponse = {
  current?: Record<string, unknown>;
};

function finiteNumber(value: unknown, minimum: number, maximum: number) {
  const number = typeof value === "number" ? value : Number(value);
  if (!Number.isFinite(number) || number < minimum || number > maximum) {
    throw new Error("Weather service returned invalid measurements");
  }
  return number;
}

function endpoint() {
  const configured = process.env.NEXT_PUBLIC_WEATHER_URL ?? DEFAULT_WEATHER_URL;
  const url = new URL(configured);
  const local = url.hostname === "localhost" || url.hostname === "127.0.0.1";
  if (url.protocol !== "https:" && !(process.env.NODE_ENV === "development" && local)) {
    throw new Error("Weather endpoint must use HTTPS");
  }
  return url;
}

function conditionFor(code: number) {
  if (code === 0) return "Clear";
  if (code <= 3) return "Cloudy";
  if ([45, 48].includes(code)) return "Fog";
  if (code <= 57) return "Drizzle";
  if (code <= 67) return "Rain";
  if (code <= 77) return "Snow";
  if (code <= 82) return "Rain showers";
  if (code <= 86) return "Snow showers";
  if (code >= 95) return "Thunderstorm";
  return "Mixed conditions";
}

function midpoint(origin: Coordinate, destination: Coordinate) {
  const latitude = (origin.latitude + destination.latitude) / 2;
  const longitude = (origin.longitude + destination.longitude) / 2;
  if (!Number.isFinite(latitude) || !Number.isFinite(longitude)) {
    throw new Error("Route coordinates are invalid");
  }
  return { latitude, longitude };
}

export async function fetchRouteWeather(
  origin: Coordinate,
  destination: Coordinate,
  signal?: AbortSignal,
): Promise<RouteWeather> {
  const point = midpoint(origin, destination);
  const url = endpoint();
  url.search = new URLSearchParams({
    // City-scale weather does not need street-level coordinates. Rounding to
    // roughly 1 km avoids disclosing a precise route or device position.
    latitude: point.latitude.toFixed(2),
    longitude: point.longitude.toFixed(2),
    current:
      "temperature_2m,apparent_temperature,precipitation,weather_code,wind_speed_10m,visibility",
    timezone: "auto",
  }).toString();

  const timeout = AbortSignal.timeout(REQUEST_TIMEOUT_MS);
  const response = await fetch(url, {
    headers: { Accept: "application/json" },
    credentials: "omit",
    referrerPolicy: "no-referrer",
    signal: signal ? AbortSignal.any([signal, timeout]) : timeout,
  });
  if (!response.ok) throw new Error(`Weather service unavailable (${response.status})`);
  const body = (await response.json()) as OpenMeteoResponse;
  const current = body.current;
  if (!current) throw new Error("Weather service returned no current conditions");

  const temperatureC = finiteNumber(current.temperature_2m, -80, 65);
  const apparentTemperatureC = finiteNumber(current.apparent_temperature, -100, 80);
  const precipitationMm = finiteNumber(current.precipitation, 0, 500);
  const windSpeedKmh = finiteNumber(current.wind_speed_10m, 0, 500);
  const visibilityMetres = finiteNumber(current.visibility, 0, 100_000);
  const weatherCode = Math.round(finiteNumber(current.weather_code, 0, 99));
  const observedAt = typeof current.time === "string" ? current.time : new Date().toISOString();
  const riskPenalty = Math.min(
    20,
    Math.round(
      precipitationMm * 2.5 +
        Math.max(0, windSpeedKmh - 35) * 0.15 +
        Math.max(0, 5_000 - visibilityMetres) / 600 +
        (weatherCode >= 95 ? 8 : 0),
    ),
  );
  const factors = [
    ...(precipitationMm > 0.2 ? ["Rain"] : []),
    ...(windSpeedKmh > 35 ? ["Strong wind"] : []),
    ...(visibilityMetres < 5_000 ? ["Low visibility"] : []),
    ...(weatherCode >= 95 ? ["Thunderstorm"] : []),
  ];

  return {
    temperatureC,
    apparentTemperatureC,
    precipitationMm,
    windSpeedKmh,
    visibilityKm: Math.round((visibilityMetres / 1_000) * 10) / 10,
    weatherCode,
    observedAt,
    condition: conditionFor(weatherCode),
    riskLabel: riskPenalty >= 10 ? "High" : riskPenalty >= 4 ? "Moderate" : "Low",
    riskPenalty,
    factors,
  };
}

export function applyWeatherRisk(
  routes: RouteOption[],
  weather: RouteWeather,
  preference: RoutePreference,
) {
  const adjusted = routes.map((route) => {
    const safetyScore = Math.max(0, route.safetyScore - weather.riskPenalty);
    const factors = [...weather.factors, ...route.factors].filter(
      (factor, index, all) => all.indexOf(factor) === index,
    );
    return {
      ...route,
      safetyScore,
      riskLevel:
        safetyScore >= 80 ? "low" as const : safetyScore >= 60 ? "medium" as const : safetyScore >= 40 ? "high" as const : "critical" as const,
      factors: factors.slice(0, 3),
      breakdown: {
        ...route.breakdown,
        weather: Math.round((route.breakdown.weather + weather.riskPenalty) * 10) / 10,
      },
      explanation: `${route.explanation} Current corridor weather: ${weather.condition.toLowerCase()} with ${weather.riskLabel.toLowerCase()} weather risk.`,
      recommended: false,
    };
  });
  const fastest = Math.min(...adjusted.map((route) => route.durationMinutes));
  const weights: Record<RoutePreference, [number, number]> = {
    safest: [0.9, 0.1],
    balanced: [0.75, 0.25],
    fastest: [0.35, 0.65],
  };
  const [safetyWeight, timeWeight] = weights[preference];
  const winner = adjusted.reduce((best, route) =>
    route.safetyScore * safetyWeight + (100 * fastest / route.durationMinutes) * timeWeight >
    best.safetyScore * safetyWeight + (100 * fastest / best.durationMinutes) * timeWeight ? route : best,
  );
  winner.recommended = true;
  return adjusted;
}
