import type { CrimePrecinct } from "./hazards";

/**
 * "Areas to review" used to be a hardcoded list of invented zones. Now that
 * reported vehicle-crime figures are available per police precinct, the panel
 * is derived from that instead.
 *
 * Nothing is synthesised here: the figures shown are reported counts and the
 * band comes from a precinct's rank among its peers. Where the data is absent
 * the caller shows an unavailable state rather than falling back to invented
 * numbers, which would look identical to real ones.
 */
export type RiskArea = {
  code: string;
  name: string;
  level: "High" | "Medium" | "Low";
  perKm2: number;
  areaKm2: number;
  topCategory: string | null;
  topCategoryCount: number;
};

export function riskLevelFromPercentile(percentile: number): RiskArea["level"] {
  if (percentile >= 0.8) return "High";
  if (percentile >= 0.5) return "Medium";
  return "Low";
}

export function topRiskAreas(precincts: CrimePrecinct[], limit = 4): RiskArea[] {
  return [...precincts]
    .sort((a, b) => (b.per_km2 ?? 0) - (a.per_km2 ?? 0))
    .slice(0, limit)
    .map((precinct) => {
      const entries = Object.entries(precinct.breakdown ?? {});
      entries.sort((a, b) => b[1] - a[1]);
      const [label, count] = entries[0] ?? [null, 0];
      return {
        code: precinct.code,
        name: precinct.name,
        level: riskLevelFromPercentile(precinct.percentile ?? 0),
        perKm2: precinct.per_km2 ?? 0,
        areaKm2: precinct.area_km2 ?? 0,
        topCategory: label,
        topCategoryCount: count,
      };
    });
}
