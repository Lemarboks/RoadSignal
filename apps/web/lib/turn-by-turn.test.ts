import { describe, expect, it } from "vitest";
import { formatStepDistance, turnByTurnState } from "./turn-by-turn";
import type { RouteStep } from "@roadsignal/types";

const steps: RouteStep[] = [
  { instruction: "Head north", maneuver: "depart", streetName: "Long Street", distanceMeters: 2000, durationSeconds: 120, location: { latitude: 0, longitude: 0 } },
  { instruction: "Turn left onto N2", maneuver: "turn-left", streetName: "N2", distanceMeters: 6000, durationSeconds: 300, location: { latitude: 0.01, longitude: 0.01 } },
  { instruction: "Arrive at your destination", maneuver: "arrive", streetName: "", distanceMeters: 0, durationSeconds: 0, location: { latitude: 0.02, longitude: 0.02 } },
];
const totalDistanceKm = 8; // 2km + 6km, matching the steps above

describe("turnByTurnState", () => {
  it("starts on the first step with the full distance remaining", () => {
    const state = turnByTurnState(steps, 0, totalDistanceKm, 40);
    expect(state.currentStepIndex).toBe(0);
    expect(state.currentStep?.maneuver).toBe("depart");
    expect(state.distanceToNextStepMeters).toBe(2000);
    expect(state.remainingDistanceKm).toBe(8);
    expect(state.remainingMinutes).toBe(40);
  });

  it("advances to the next step once its distance has been covered", () => {
    // 2km of 8km travelled == 25% progress, right at the first turn.
    const state = turnByTurnState(steps, 25, totalDistanceKm, 40);
    expect(state.currentStepIndex).toBe(1);
    expect(state.currentStep?.maneuver).toBe("turn-left");
    expect(state.nextStep?.maneuver).toBe("arrive");
    expect(state.distanceToNextStepMeters).toBe(6000);
  });

  it("reaches the arrival step at full progress", () => {
    const state = turnByTurnState(steps, 100, totalDistanceKm, 40);
    expect(state.currentStep?.maneuver).toBe("arrive");
    expect(state.nextStep).toBeNull();
    expect(state.remainingDistanceKm).toBe(0);
    expect(state.remainingMinutes).toBe(0);
  });

  it("returns no current step when the route has none", () => {
    const state = turnByTurnState([], 50, totalDistanceKm, 40);
    expect(state.currentStepIndex).toBe(-1);
    expect(state.currentStep).toBeNull();
    expect(state.remainingDistanceKm).toBe(4);
    expect(state.remainingMinutes).toBe(20);
  });

  it("clamps out-of-range progress values", () => {
    expect(turnByTurnState(steps, -10, totalDistanceKm, 40).remainingDistanceKm).toBe(8);
    expect(turnByTurnState(steps, 150, totalDistanceKm, 40).remainingDistanceKm).toBe(0);
  });
});

describe("formatStepDistance", () => {
  it("shows 'now' for very short distances", () => {
    expect(formatStepDistance(10)).toBe("now");
  });

  it("shows metres rounded to the nearest ten below 1km", () => {
    expect(formatStepDistance(124)).toBe("120 m");
  });

  it("shows kilometres with one decimal at or above 1km", () => {
    expect(formatStepDistance(1700)).toBe("1.7 km");
  });
});
