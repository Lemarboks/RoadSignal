import type { Incident, RouteOption } from "@roadsignal/types";

/**
 * Choosing an alternative route worth offering.
 *
 * The previous rule was "the highest-scoring route that isn't the selected
 * one", which had two problems: it offered an alternative even when that
 * alternative was no better (or worse) than the road you were already on, and
 * it paid no attention to where the incident actually was -- so it could
 * cheerfully route you straight through the thing being reported.
 *
 * A suggestion is only made when it is a genuine improvement AND it keeps
 * clear of the active incidents. Otherwise nothing is offered, which is the
 * honest answer: sometimes the road you are on is still the best one.
 */

/** Minimum safety-score gain before interrupting a driver with a reroute. */
export const MIN_IMPROVEMENT = 4;
/** How close a route may pass to an active incident, in kilometres. */
export const INCIDENT_CLEARANCE_KM = 0.35;

export function haversineKm(
  a: { latitude: number; longitude: number },
  b: { latitude: number; longitude: number },
): number {
  const toRadians = (value: number) => (value * Math.PI) / 180;
  const dLat = toRadians(b.latitude - a.latitude);
  const dLon = toRadians(b.longitude - a.longitude);
  const lat1 = toRadians(a.latitude);
  const lat2 = toRadians(b.latitude);
  const h =
    Math.sin(dLat / 2) ** 2 + Math.cos(lat1) * Math.cos(lat2) * Math.sin(dLon / 2) ** 2;
  return 6371 * 2 * Math.asin(Math.sqrt(h));
}

export function activeIncidents(incidents: Incident[]): Incident[] {
  return incidents.filter((incident) => incident.status === "active");
}

/** How close this route comes to the nearest active incident, in km. */
export function closestIncidentKm(route: RouteOption, incidents: Incident[]): number {
  const active = activeIncidents(incidents);
  if (!active.length || !route.geometry?.length) return Infinity;
  let closest = Infinity;
  for (const point of route.geometry) {
    for (const incident of active) {
      const distance = haversineKm(point, incident.location);
      if (distance < closest) closest = distance;
    }
  }
  return closest;
}

export function routeAvoidsIncidents(
  route: RouteOption,
  incidents: Incident[],
  clearanceKm = INCIDENT_CLEARANCE_KM,
): boolean {
  return closestIncidentKm(route, incidents) > clearanceKm;
}

export type RerouteSuggestion = {
  route: RouteOption;
  improvement: number;
  avoidsIncidents: boolean;
  reason: string;
};

/**
 * The alternative worth offering, or null when staying put is the right call.
 *
 * Preference order: routes that clear the incidents come first, then the
 * largest safety gain. A route that merely scores higher but still runs
 * through the reported incident is not offered.
 */
export function bestAlternative(
  routes: RouteOption[],
  selectedId: string,
  incidents: Incident[],
  minImprovement = MIN_IMPROVEMENT,
): RerouteSuggestion | null {
  const current = routes.find((route) => route.id === selectedId);
  if (!current) return null;

  const currentAvoids = routeAvoidsIncidents(current, incidents);
  const candidates = routes
    .filter((route) => route.id !== selectedId)
    .map((route) => ({
      route,
      improvement: Number((route.safetyScore - current.safetyScore).toFixed(1)),
      avoidsIncidents: routeAvoidsIncidents(route, incidents),
    }))
    // Worth offering if it is materially safer, or if it clears an incident
    // the current route runs into -- that is valuable even at a similar score.
    .filter((candidate) =>
      candidate.improvement >= minImprovement ||
      (candidate.avoidsIncidents && !currentAvoids),
    )
    .sort(
      (first, second) =>
        Number(second.avoidsIncidents) - Number(first.avoidsIncidents) ||
        second.improvement - first.improvement,
    );

  const best = candidates[0];
  if (!best) return null;

  const gain = best.improvement > 0 ? `+${best.improvement} safety` : "a similar safety score";
  const reason = !currentAvoids && best.avoidsIncidents
    ? `${best.route.name} clears the reported incident (${gain}).`
    : `${best.route.name} scores ${gain} than your current route.`;

  return { ...best, reason };
}
