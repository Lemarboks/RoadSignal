export type RiskLevel = "low" | "medium" | "high" | "critical";
export type RoutePreference = "safest" | "balanced" | "fastest";
export type Coordinate = { latitude: number; longitude: number };
export type RiskBreakdown = { crime: number; accident: number; traffic: number; weather: number; roadCondition: number; community: number };
export type RouteOption = {
  id: string; name: string; durationMinutes: number; distanceKm: number; safetyScore: number;
  confidence: number; riskLevel: RiskLevel; recommended: boolean; differenceFromFastest: number;
  factors: string[]; breakdown: RiskBreakdown; explanation: string; geometry: Coordinate[];
};
export type Incident = {
  id: string; incidentType: string; severity: number; sourceType: string; verificationStatus: string;
  confidence: number; description: string; occurredAt: string; expiresAt: string | null; location: Coordinate;
  confirmations: number; disputes: number; status: "active" | "resolved" | "expired";
};
export type Trip = { id: string; routeId: string; status: "active" | "paused" | "completed"; progress: number; safetyScore: number; alerts: string[] };
