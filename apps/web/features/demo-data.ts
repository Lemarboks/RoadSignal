import type { Incident, RouteOption } from "@roadsignal/types";
import type { ResolvedPlace } from "../lib/open-routing";
import { demoRouteGeometry } from "../lib/demo-route-geometry";

export type FleetAnalytics = {
  active_drivers: number;
  high_risk_drivers: number;
  average_safety_score: number;
  active_incidents: number;
  trips_completed_today: number;
};

export const demoFleetAnalytics: FleetAnalytics = {
  active_drivers: 3,
  high_risk_drivers: 1,
  average_safety_score: 84.2,
  active_incidents: 2,
  trips_completed_today: 20,
};

export const demoDrivers = [
  {
    name: "Amina Daniels",
    vehicle: "CA 482-771",
    status: "On trip",
    route: "CBD to Airport",
    score: 87,
    updated: "Now",
  },
  {
    name: "Lwazi Mbeki",
    vehicle: "CA 193-044",
    status: "Attention",
    route: "Woodstock to Bellville",
    score: 58,
    updated: "2 min ago",
  },
  {
    name: "Nadia Jacobs",
    vehicle: "CY 827-519",
    status: "Available",
    route: "No active trip",
    score: 92,
    updated: "6 min ago",
  },
  {
    name: "Ethan Williams",
    vehicle: "CA 614-208",
    status: "Offline",
    route: "Last trip: Pinelands",
    score: 76,
    updated: "28 min ago",
  },
] as const;

export const demoRiskZones = [
  {
    area: "Hospital Bend",
    level: "High",
    score: 48,
    signal: "Recent collision",
    confidence: "86%",
  },
  {
    area: "Athlone",
    level: "Medium",
    score: 64,
    signal: "Community reports",
    confidence: "72%",
  },
  {
    area: "Woodstock",
    level: "Medium",
    score: 71,
    signal: "Traffic disruption",
    confidence: "79%",
  },
  {
    area: "Pinelands",
    level: "Low",
    score: 88,
    signal: "No active reports",
    confidence: "81%",
  },
] as const;

export const fallbackRoutes: RouteOption[] = [
  {
    id: "route-balanced",
    name: "Balanced Route",
    durationMinutes: 28,
    distanceKm: 25.5,
    safetyScore: 87,
    confidence: 0.84,
    riskLevel: "low",
    recommended: true,
    differenceFromFastest: 8,
    factors: ["Traffic", "Road condition"],
    breakdown: {
      crime: 5,
      accident: 3,
      traffic: 6,
      weather: 1,
      roadCondition: 2,
      community: 1,
    },
    explanation:
      "Eight minutes longer, following a distinct road corridor around recent demonstration incidents.",
    geometry: demoRouteGeometry["route-balanced"],
  },
  {
    id: "route-safest",
    name: "Safest Route",
    durationMinutes: 30,
    distanceKm: 24.6,
    safetyScore: 92,
    confidence: 0.81,
    riskLevel: "low",
    recommended: false,
    differenceFromFastest: 10,
    factors: ["Traffic", "Weather"],
    breakdown: {
      crime: 3,
      accident: 2,
      traffic: 4,
      weather: 1,
      roadCondition: 1,
      community: 1,
    },
    explanation:
      "Lowest known demonstration exposure, with ten additional travel minutes.",
    geometry: demoRouteGeometry["route-safest"],
  },
  {
    id: "route-fastest",
    name: "Fastest Route",
    durationMinutes: 20,
    distanceKm: 19.9,
    safetyScore: 63,
    confidence: 0.88,
    riskLevel: "medium",
    recommended: false,
    differenceFromFastest: 0,
    factors: ["Crime", "Accident"],
    breakdown: {
      crime: 14,
      accident: 11,
      traffic: 8,
      weather: 1,
      roadCondition: 4,
      community: 3,
    },
    explanation:
      "Fastest arrival, but passes recent collision and vehicle-crime reports.",
    geometry: demoRouteGeometry["route-fastest"],
  },
];

export const initialIncidents: Incident[] = [
  {
    id: "demo-1",
    incidentType: "Accident",
    severity: 4,
    sourceType: "Traffic provider",
    verificationStatus: "confirmed",
    confidence: 0.86,
    description: "Collision near Hospital Bend",
    occurredAt: new Date(Date.now() - 2_100_000).toISOString(),
    expiresAt: null,
    location: { latitude: -33.941, longitude: 18.452 },
    confirmations: 4,
    disputes: 0,
    status: "active",
  },
];

export const defaultOrigin: ResolvedPlace = {
  displayName:
    "Cape Town City Centre, City of Cape Town, Western Cape, South Africa",
  latitude: -33.9249,
  longitude: 18.4241,
};

export const defaultDestination: ResolvedPlace = {
  displayName:
    "Cape Town International Airport, City of Cape Town, Western Cape, South Africa",
  latitude: -33.9715,
  longitude: 18.6021,
};
