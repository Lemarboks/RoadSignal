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

export type DemoDriver = {
  name: string;
  vehicle: string;
  status: "On trip" | "Attention" | "Available" | "Offline";
  route: string;
  score: number;
  updated: string;
  activeTrip?: {
    routeId: string;
    origin: string;
    destination: string;
    currentRoad: string;
    progress: number;
    etaMinutes: number;
    alerts: string[];
  };
};

export const demoDrivers: readonly DemoDriver[] = [
  {
    name: "Amina Daniels",
    vehicle: "CA 482-771",
    status: "On trip",
    route: "CBD to Airport",
    score: 87,
    updated: "Now",
    activeTrip: {
      routeId: "route-balanced",
      origin: "Cape Town CBD",
      destination: "Cape Town International Airport",
      currentRoad: "Settlers Way",
      progress: 64,
      etaMinutes: 11,
      alerts: [],
    },
  },
  {
    name: "Lwazi Mbeki",
    vehicle: "CA 193-044",
    status: "Attention",
    route: "Woodstock to Bellville",
    score: 58,
    updated: "2 min ago",
    activeTrip: {
      routeId: "route-fastest",
      origin: "Woodstock",
      destination: "Bellville",
      currentRoad: "N1 inbound near Maitland",
      progress: 38,
      etaMinutes: 19,
      alerts: [
        "Elevated incident risk ahead near the Maitland interchange. Review the safer alternative.",
      ],
    },
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
];

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
    steps: [
      { instruction: "Head northeast on Buitengracht Street", maneuver: "depart", streetName: "Buitengracht Street", distanceMeters: 900, durationSeconds: 150, location: { latitude: -33.925071, longitude: 18.423921 } },
      { instruction: "Turn right onto the N1", maneuver: "turn-right", streetName: "N1", distanceMeters: 8200, durationSeconds: 420, location: { latitude: -33.943386, longitude: 18.464726 } },
      { instruction: "Keep left to continue onto the N2", maneuver: "slight-left", streetName: "N2", distanceMeters: 7600, durationSeconds: 390, location: { latitude: -33.967982, longitude: 18.495323 } },
      { instruction: "Turn left onto Borcherds Quarry Road", maneuver: "turn-left", streetName: "Borcherds Quarry Road", distanceMeters: 6100, durationSeconds: 330, location: { latitude: -33.950243, longitude: 18.523544 } },
      { instruction: "Turn right onto Airport Approach Road", maneuver: "turn-right", streetName: "Airport Approach Road", distanceMeters: 2700, durationSeconds: 180, location: { latitude: -33.978315, longitude: 18.58856 } },
      { instruction: "Arrive at Cape Town International Airport", maneuver: "arrive", streetName: "", distanceMeters: 0, durationSeconds: 0, location: { latitude: -33.973045, longitude: 18.598498 } },
    ],
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
    steps: [
      { instruction: "Head northeast on Buitengracht Street", maneuver: "depart", streetName: "Buitengracht Street", distanceMeters: 900, durationSeconds: 150, location: { latitude: -33.925071, longitude: 18.423921 } },
      { instruction: "Turn right onto Somerset Road", maneuver: "turn-right", streetName: "Somerset Road", distanceMeters: 6400, durationSeconds: 360, location: { latitude: -33.929039, longitude: 18.462602 } },
      { instruction: "Continue onto Eastern Boulevard", maneuver: "straight", streetName: "Eastern Boulevard", distanceMeters: 8900, durationSeconds: 450, location: { latitude: -33.923589, longitude: 18.517545 } },
      { instruction: "Turn right onto Vanguard Drive", maneuver: "turn-right", streetName: "Vanguard Drive", distanceMeters: 5300, durationSeconds: 300, location: { latitude: -33.947184, longitude: 18.508928 } },
      { instruction: "Turn left onto Airport Approach Road", maneuver: "turn-left", streetName: "Airport Approach Road", distanceMeters: 2900, durationSeconds: 190, location: { latitude: -33.980419, longitude: 18.587966 } },
      { instruction: "Arrive at Cape Town International Airport", maneuver: "arrive", streetName: "", distanceMeters: 0, durationSeconds: 0, location: { latitude: -33.973045, longitude: 18.598498 } },
    ],
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
    steps: [
      { instruction: "Head southeast on Strand Street", maneuver: "depart", streetName: "Strand Street", distanceMeters: 700, durationSeconds: 120, location: { latitude: -33.925071, longitude: 18.423921 } },
      { instruction: "Turn left onto the N2", maneuver: "turn-left", streetName: "N2", distanceMeters: 6900, durationSeconds: 330, location: { latitude: -33.936871, longitude: 18.453205 } },
      { instruction: "Continue straight on the N2", maneuver: "straight", streetName: "N2", distanceMeters: 8700, durationSeconds: 390, location: { latitude: -33.94658, longitude: 18.488635 } },
      { instruction: "Keep right toward Settlers Way", maneuver: "slight-right", streetName: "Settlers Way", distanceMeters: 2200, durationSeconds: 120, location: { latitude: -33.96452, longitude: 18.570254 } },
      { instruction: "Turn right onto Airport Approach Road", maneuver: "turn-right", streetName: "Airport Approach Road", distanceMeters: 1400, durationSeconds: 90, location: { latitude: -33.974554, longitude: 18.590001 } },
      { instruction: "Arrive at Cape Town International Airport", maneuver: "arrive", streetName: "", distanceMeters: 0, durationSeconds: 0, location: { latitude: -33.973045, longitude: 18.598498 } },
    ],
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
