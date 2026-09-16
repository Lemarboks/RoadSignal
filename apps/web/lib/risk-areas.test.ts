import { describe, expect, it } from "vitest";
import { riskLevelFromPercentile, topRiskAreas } from "./risk-areas";
import type { CrimePrecinct } from "./hazards";

function precinct(overrides: Partial<CrimePrecinct>): CrimePrecinct {
  return {
    code: "PD1",
    name: "Somewhere",
    rings: [],
    per_km2: 10,
    rate_per_100k: 100,
    percentile: 0.5,
    crime_baseline: 15,
    weighted_incidents: 50,
    breakdown: {},
    population: 10_000,
    area_km2: 5,
    ...overrides,
  };
}

describe("riskLevelFromPercentile", () => {
  it("bands by rank among peers", () => {
    expect(riskLevelFromPercentile(0.95)).toBe("High");
    expect(riskLevelFromPercentile(0.8)).toBe("High");
    expect(riskLevelFromPercentile(0.6)).toBe("Medium");
    expect(riskLevelFromPercentile(0.2)).toBe("Low");
    expect(riskLevelFromPercentile(0)).toBe("Low");
  });
});

describe("topRiskAreas", () => {
  it("ranks by reported density, highest first", () => {
    const areas = topRiskAreas([
      precinct({ code: "A", name: "Quiet", per_km2: 3 }),
      precinct({ code: "B", name: "Busy", per_km2: 300 }),
      precinct({ code: "C", name: "Middling", per_km2: 40 }),
    ]);
    expect(areas.map((area) => area.name)).toEqual(["Busy", "Middling", "Quiet"]);
  });

  it("surfaces the largest reported category with its real count", () => {
    const [area] = topRiskAreas([
      precinct({
        name: "Nyanga",
        per_km2: 320,
        percentile: 0.98,
        breakdown: { Carjacking: 213, "Common robbery": 561, "Truck hijacking": 3 },
      }),
    ]);
    expect(area.topCategory).toBe("Common robbery");
    expect(area.topCategoryCount).toBe(561);
    expect(area.level).toBe("High");
  });

  it("reports no category rather than inventing one when nothing was reported", () => {
    const [area] = topRiskAreas([precinct({ breakdown: {}, per_km2: 0, percentile: 0.01 })]);
    expect(area.topCategory).toBeNull();
    expect(area.topCategoryCount).toBe(0);
    expect(area.level).toBe("Low");
  });

  it("returns nothing when there is no data, so callers cannot fall back to invented zones", () => {
    expect(topRiskAreas([])).toEqual([]);
  });

  it("limits the list", () => {
    const many = Array.from({ length: 12 }, (_, index) =>
      precinct({ code: `P${index}`, per_km2: index }),
    );
    expect(topRiskAreas(many)).toHaveLength(4);
    expect(topRiskAreas(many, 2)).toHaveLength(2);
  });
});
