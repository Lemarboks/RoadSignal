import type {
  Coordinate,
  Incident,
  RiskBreakdown,
  RouteOption,
  RoutePreference,
} from "@saferoute/types";

const NOMINATIM_URL =
  process.env.NEXT_PUBLIC_GEOCODER_URL ??
  "https://nominatim.openstreetmap.org/search";
const PHOTON_URL =
  process.env.NEXT_PUBLIC_SEARCH_URL ?? "https://photon.komoot.io/api/";
const OSRM_URL =
  process.env.NEXT_PUBLIC_ROUTER_URL ??
  "https://routing.openstreetmap.de/routed-car/route/v1/driving";
const CAPE_TOWN_VIEWBOX = "18.28,-33.74,18.98,-34.36";
const CACHE_PREFIX = "saferoute:place:";
const PUBLIC_REQUEST_TIMEOUT_MS = 8_000;

function requestSignal(signal?: AbortSignal) {
  const timeout = AbortSignal.timeout(PUBLIC_REQUEST_TIMEOUT_MS);
  return signal ? AbortSignal.any([signal, timeout]) : timeout;
}

export type ResolvedPlace = Coordinate & {
  displayName: string;
};

type NominatimResult = {
  display_name: string;
  lat: string;
  lon: string;
};

type PhotonResponse = {
  features: Array<{
    geometry: { coordinates: [number, number] };
    properties: {
      name?: string;
      street?: string;
      housenumber?: string;
      suburb?: string;
      district?: string;
      city?: string;
      state?: string;
      country?: string;
    };
  }>;
};

type OsrmRoute = {
  distance: number;
  duration: number;
  geometry: { coordinates: [number, number][] };
  legs: Array<{
    steps?: Array<{ name: string; ref?: string }>;
  }>;
};

type OsrmResponse = {
  code: string;
  routes?: OsrmRoute[];
  message?: string;
};

type RiskZone = Coordinate & {
  radiusKm: number;
  factors: Partial<Record<keyof RiskBreakdown, number>>;
};

const RISK_ZONES: RiskZone[] = [
  {
    latitude: -33.941,
    longitude: 18.452,
    radiusKm: 2.1,
    factors: { accident: 18, traffic: 13 },
  },
  {
    latitude: -33.963,
    longitude: 18.478,
    radiusKm: 3.2,
    factors: { crime: 17, community: 6 },
  },
  {
    latitude: -33.961,
    longitude: 18.503,
    radiusKm: 3.4,
    factors: { crime: 14, roadCondition: 7 },
  },
  {
    latitude: -33.925,
    longitude: 18.424,
    radiusKm: 2.4,
    factors: { traffic: 11, community: 3 },
  },
  {
    latitude: -33.981,
    longitude: 18.531,
    radiusKm: 2.8,
    factors: { traffic: 9, accident: 6 },
  },
  {
    latitude: -34.02,
    longitude: 18.46,
    radiusKm: 4,
    factors: { weather: 7, roadCondition: 5 },
  },
];

export class PlaceNotFoundError extends Error {
  constructor(query: string) {
    super(
      `No Cape Town location matched "${query}". Add a suburb or street name and try again.`,
    );
    this.name = "PlaceNotFoundError";
  }
}

export async function searchPlaceSuggestions(
  query: string,
  signal?: AbortSignal,
): Promise<ResolvedPlace[]> {
  const trimmed = query.trim();
  if (trimmed.length < 3) return [];
  const parameters = new URLSearchParams({
    q: trimmed,
    bbox: "18.28,-34.36,19.05,-33.70",
    countrycode: "ZA",
    lat: "-33.9249",
    lon: "18.4241",
    zoom: "11",
    location_bias_scale: "0.2",
    lang: "en",
    limit: "5",
  });
  const response = await fetch(`${PHOTON_URL}?${parameters}`, {
    signal: requestSignal(signal),
  });
  if (!response.ok) return [];
  const body = (await response.json()) as PhotonResponse;
  return body.features.map((feature) => {
    const properties = feature.properties;
    const street = [properties.housenumber, properties.street]
      .filter(Boolean)
      .join(" ");
    const displayName = [
      properties.name || street,
      properties.suburb || properties.district,
      properties.city,
      properties.state,
      properties.country,
    ]
      .filter((value, index, values): value is string =>
        Boolean(value && values.indexOf(value) === index),
      )
      .join(", ");
    return {
      displayName: displayName || trimmed,
      longitude: feature.geometry.coordinates[0],
      latitude: feature.geometry.coordinates[1],
    };
  });
}

function cacheKey(query: string) {
  return `${CACHE_PREFIX}${query.trim().toLocaleLowerCase()}`;
}

function readCachedPlace(query: string): ResolvedPlace | null {
  try {
    const value = localStorage.getItem(cacheKey(query));
    return value ? (JSON.parse(value) as ResolvedPlace) : null;
  } catch {
    return null;
  }
}

function cachePlace(query: string, place: ResolvedPlace) {
  try {
    localStorage.setItem(cacheKey(query), JSON.stringify(place));
  } catch {
    // Storage can be unavailable in privacy mode; routing still works without it.
  }
}

export async function resolvePlace(query: string): Promise<ResolvedPlace> {
  const trimmed = query.trim();
  if (trimmed.length < 2)
    throw new PlaceNotFoundError(trimmed || "empty search");
  const cached = readCachedPlace(trimmed);
  if (cached) return cached;

  const parameters = new URLSearchParams({
    q: trimmed,
    format: "jsonv2",
    limit: "5",
    countrycodes: "za",
    viewbox: CAPE_TOWN_VIEWBOX,
    bounded: "1",
    addressdetails: "1",
    "accept-language": "en",
  });
  const response = await fetch(`${NOMINATIM_URL}?${parameters}`, {
    headers: { Accept: "application/json" },
    signal: requestSignal(),
  });
  if (!response.ok) throw new Error(`Place search failed (${response.status})`);
  const matches = (await response.json()) as NominatimResult[];
  const match = matches[0];
  if (!match) throw new PlaceNotFoundError(trimmed);

  const place = {
    displayName: match.display_name,
    latitude: Number(match.lat),
    longitude: Number(match.lon),
  };
  cachePlace(trimmed, place);
  return place;
}

function haversineKm(first: Coordinate, second: Coordinate) {
  const radians = (degrees: number) => (degrees * Math.PI) / 180;
  const latitudeDelta = radians(second.latitude - first.latitude);
  const longitudeDelta = radians(second.longitude - first.longitude);
  const firstLatitude = radians(first.latitude);
  const secondLatitude = radians(second.latitude);
  const value =
    Math.sin(latitudeDelta / 2) ** 2 +
    Math.cos(firstLatitude) *
      Math.cos(secondLatitude) *
      Math.sin(longitudeDelta / 2) ** 2;
  return 6371 * 2 * Math.atan2(Math.sqrt(value), Math.sqrt(1 - value));
}

function proximity(distanceKm: number, radiusKm: number) {
  return Math.exp(-distanceKm / radiusKm);
}

function sampledGeometry(geometry: Coordinate[]) {
  const step = Math.max(1, Math.floor(geometry.length / 80));
  const points = geometry.filter((_, index) => index % step === 0);
  const last = geometry.at(-1);
  if (last && points.at(-1) !== last) points.push(last);
  return points;
}

function scoreGeometry(geometry: Coordinate[], incidents: Incident[]) {
  const samples = sampledGeometry(geometry);
  const totals: RiskBreakdown = {
    crime: 0,
    accident: 0,
    traffic: 0,
    weather: 0,
    roadCondition: 0,
    community: 0,
  };
  let worstPointPenalty = 0;

  for (const point of samples) {
    const pointPenalties: RiskBreakdown = {
      crime: 0,
      accident: 0,
      traffic: 0,
      weather: 0,
      roadCondition: 0,
      community: 0,
    };
    for (const zone of RISK_ZONES) {
      const decay = proximity(haversineKm(point, zone), zone.radiusKm);
      for (const [factor, penalty] of Object.entries(zone.factors)) {
        pointPenalties[factor as keyof RiskBreakdown] +=
          Number(penalty) * decay;
      }
    }
    for (const incident of incidents.filter(
      (item) => item.status === "active",
    )) {
      const distance = haversineKm(point, incident.location);
      const impact =
        incident.severity *
        incident.confidence *
        proximity(distance, 1.8) *
        1.7;
      const type = incident.incidentType.toLocaleLowerCase();
      const factor: keyof RiskBreakdown = type.includes("accident")
        ? "accident"
        : type.includes("robbery") ||
            type.includes("crime") ||
            type.includes("hijack")
          ? "crime"
          : type.includes("flood")
            ? "weather"
            : type.includes("pothole") || type.includes("road condition")
              ? "roadCondition"
              : type.includes("traffic") || type.includes("closure")
                ? "traffic"
                : "community";
      pointPenalties[factor] += impact;
    }
    for (const factor of Object.keys(totals) as (keyof RiskBreakdown)[]) {
      totals[factor] += pointPenalties[factor] / Math.max(samples.length, 1);
    }
    worstPointPenalty = Math.max(
      worstPointPenalty,
      Object.values(pointPenalties).reduce((sum, value) => sum + value, 0),
    );
  }

  const weights: Record<keyof RiskBreakdown, number> = {
    crime: 0.35,
    accident: 0.25,
    traffic: 0.15,
    weather: 0.1,
    roadCondition: 0.1,
    community: 0.05,
  };
  const averagePenalty = (
    Object.keys(totals) as (keyof RiskBreakdown)[]
  ).reduce((sum, factor) => sum + totals[factor] * weights[factor] * 2.8, 0);
  const averageScore = Math.max(0, 100 - averagePenalty);
  const worstScore = Math.max(0, 100 - worstPointPenalty * 0.75);
  const confidence = 0.82;
  const confidenceAdjusted = averageScore * (0.75 + 0.25 * confidence);
  const safetyScore = Math.round(
    Math.max(
      0,
      Math.min(
        100,
        0.5 * averageScore + 0.3 * worstScore + 0.2 * confidenceAdjusted,
      ),
    ),
  );

  return {
    safetyScore,
    confidence,
    breakdown: Object.fromEntries(
      Object.entries(totals).map(([factor, value]) => [
        factor,
        Math.round(value * 10) / 10,
      ]),
    ) as unknown as RiskBreakdown,
  };
}

function corridorName(route: OsrmRoute, index: number) {
  const names = route.legs
    .flatMap((leg) => leg.steps ?? [])
    .map((step) => step.ref || step.name)
    .filter((name): name is string => Boolean(name?.trim()));
  const distinct = [...new Set(names)].slice(0, 2);
  return distinct.length
    ? distinct.join(" / ")
    : `Road alternative ${index + 1}`;
}

async function requestRoutes(coordinates: Coordinate[]) {
  const coordinateString = coordinates
    .map((point) => `${point.longitude},${point.latitude}`)
    .join(";");
  const parameters = new URLSearchParams({
    alternatives: "3",
    steps: "true",
    overview: "full",
    geometries: "geojson",
  });
  const response = await fetch(`${OSRM_URL}/${coordinateString}?${parameters}`, {
    signal: requestSignal(),
  });
  if (!response.ok) throw new Error(`Road routing failed (${response.status})`);
  const body = (await response.json()) as OsrmResponse;
  if (body.code !== "Ok" || !body.routes?.length) {
    throw new Error(body.message || "No driveable route was found");
  }
  return body.routes;
}

function viaPoints(origin: Coordinate, destination: Coordinate) {
  const latitudeDelta = destination.latitude - origin.latitude;
  const longitudeDelta = destination.longitude - origin.longitude;
  const magnitude = Math.hypot(latitudeDelta, longitudeDelta) || 1;
  const offset = Math.min(0.025, Math.max(0.009, magnitude * 0.16));
  const midpoint = {
    latitude: (origin.latitude + destination.latitude) / 2,
    longitude: (origin.longitude + destination.longitude) / 2,
  };
  return [-1, 1].map((direction) => ({
    latitude:
      midpoint.latitude + direction * (-longitudeDelta / magnitude) * offset,
    longitude:
      midpoint.longitude + direction * (latitudeDelta / magnitude) * offset,
  }));
}

function geometryFingerprint(route: OsrmRoute) {
  const middle =
    route.geometry.coordinates[
      Math.floor(route.geometry.coordinates.length / 2)
    ];
  return `${Math.round(route.distance / 100)}:${middle?.map((value) => value.toFixed(3)).join(",")}`;
}

async function threeRoadAlternatives(
  origin: ResolvedPlace,
  destination: ResolvedPlace,
) {
  const direct = await requestRoutes([origin, destination]);
  const routes = [...direct];
  if (routes.length < 3) {
    for (const via of viaPoints(origin, destination)) {
      await new Promise((resolve) => setTimeout(resolve, 1050));
      try {
        const additional = await requestRoutes([origin, via, destination]);
        routes.push(additional[0]);
      } catch {
        // Continue with the alternatives already received from the public service.
      }
      if (routes.length >= 3) break;
    }
  }
  const seen = new Set<string>();
  return routes
    .filter((route) => {
      const fingerprint = geometryFingerprint(route);
      if (seen.has(fingerprint)) return false;
      seen.add(fingerprint);
      return true;
    })
    .slice(0, 3);
}

export async function analyseOpenRoutes(
  originQuery: string,
  destinationQuery: string,
  preference: RoutePreference,
  incidents: Incident[],
  resolvedOrigin?: ResolvedPlace | null,
  resolvedDestination?: ResolvedPlace | null,
) {
  // Sequential explicit lookups respect Nominatim's public-service request ceiling.
  const origin = resolvedOrigin ?? (await resolvePlace(originQuery));
  if (!resolvedOrigin && !resolvedDestination) {
    await new Promise((resolve) => setTimeout(resolve, 1050));
  }
  const destination =
    resolvedDestination ?? (await resolvePlace(destinationQuery));
  const roadRoutes = await threeRoadAlternatives(origin, destination);
  if (roadRoutes.length < 3)
    throw new Error("Three distinct road alternatives were not available");

  const fastestMinutes = Math.min(
    ...roadRoutes.map((route) => route.duration / 60),
  );
  const options: RouteOption[] = roadRoutes.map((roadRoute, index) => {
    const geometry = roadRoute.geometry.coordinates.map(
      ([longitude, latitude]) => ({
        latitude,
        longitude,
      }),
    );
    const scored = scoreGeometry(geometry, incidents);
    const durationMinutes = Math.max(1, Math.round(roadRoute.duration / 60));
    const differenceFromFastest = Math.max(
      0,
      Math.round(durationMinutes - fastestMinutes),
    );
    const factors = Object.entries(scored.breakdown)
      .sort(([, first], [, second]) => Number(second) - Number(first))
      .slice(0, 3)
      .map(([factor]) =>
        factor
          .replace(/([A-Z])/g, " $1")
          .replace(/^./, (value) => value.toUpperCase()),
      );
    return {
      id: `open-route-${index + 1}`,
      name: corridorName(roadRoute, index),
      durationMinutes,
      distanceKm: Math.round((roadRoute.distance / 1000) * 10) / 10,
      safetyScore: scored.safetyScore,
      confidence: scored.confidence,
      riskLevel:
        scored.safetyScore >= 80
          ? "low"
          : scored.safetyScore >= 60
            ? "medium"
            : scored.safetyScore >= 40
              ? "high"
              : "critical",
      recommended: false,
      differenceFromFastest,
      factors,
      breakdown: scored.breakdown,
      explanation: `This road-following alternative uses ${corridorName(roadRoute, index)} and is assessed against current demonstration incidents and Cape Town risk zones.`,
      geometry,
    };
  });

  const weights: Record<RoutePreference, [number, number]> = {
    safest: [0.9, 0.1],
    balanced: [0.75, 0.25],
    fastest: [0.35, 0.65],
  };
  const [safetyWeight, timeWeight] = weights[preference];
  const recommended = options.reduce((best, option) => {
    const utility =
      option.safetyScore * safetyWeight +
      ((100 * fastestMinutes) / option.durationMinutes) * timeWeight;
    const bestUtility =
      best.safetyScore * safetyWeight +
      ((100 * fastestMinutes) / best.durationMinutes) * timeWeight;
    return utility > bestUtility ? option : best;
  });
  recommended.recommended = true;
  recommended.name =
    preference === "fastest"
      ? "Fastest Route"
      : preference === "safest"
        ? "Safest Route"
        : "Balanced Route";

  return { routes: options, origin, destination };
}
