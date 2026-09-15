import type { RouteStep } from "@roadsignal/types";

export type TurnByTurnState = {
  currentStepIndex: number;
  currentStep: RouteStep | null;
  nextStep: RouteStep | null;
  distanceToNextStepMeters: number;
  remainingDistanceKm: number;
  remainingMinutes: number;
};

export function turnByTurnState(
  steps: RouteStep[],
  progressPercent: number,
  totalDistanceKm: number,
  totalDurationMinutes: number,
): TurnByTurnState {
  const clampedProgress = Math.min(100, Math.max(0, progressPercent));
  const remainingDistanceKm =
    Math.round(totalDistanceKm * (1 - clampedProgress / 100) * 10) / 10;
  const remainingMinutes = Math.max(
    0,
    Math.round(totalDurationMinutes * (1 - clampedProgress / 100)),
  );
  if (!steps.length) {
    return {
      currentStepIndex: -1,
      currentStep: null,
      nextStep: null,
      distanceToNextStepMeters: 0,
      remainingDistanceKm,
      remainingMinutes,
    };
  }
  const traveledMeters = (clampedProgress / 100) * totalDistanceKm * 1000;
  const cumulativeStart: number[] = [];
  let running = 0;
  for (const step of steps) {
    cumulativeStart.push(running);
    running += step.distanceMeters;
  }
  let currentStepIndex = 0;
  for (let index = 0; index < steps.length; index++) {
    if (cumulativeStart[index] <= traveledMeters) currentStepIndex = index;
    else break;
  }
  const currentStep = steps[currentStepIndex];
  const nextStep = steps[currentStepIndex + 1] ?? null;
  const stepEndMeters = cumulativeStart[currentStepIndex] + currentStep.distanceMeters;
  const distanceToNextStepMeters = Math.max(0, Math.round(stepEndMeters - traveledMeters));
  return {
    currentStepIndex,
    currentStep,
    nextStep,
    distanceToNextStepMeters,
    remainingDistanceKm,
    remainingMinutes,
  };
}

export function formatStepDistance(meters: number): string {
  if (meters < 30) return "now";
  if (meters < 1000) return `${Math.round(meters / 10) * 10} m`;
  return `${(meters / 1000).toFixed(1)} km`;
}
