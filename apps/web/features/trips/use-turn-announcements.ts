import { useEffect, useRef } from "react";
import type { RouteStep } from "@roadsignal/types";
import { speakAlert } from "../../lib/voice-alerts";

export function useTurnAnnouncements(currentStep: RouteStep | null, enabled: boolean) {
  const lastAnnounced = useRef<RouteStep | null>(null);

  useEffect(() => {
    if (!enabled || !currentStep || currentStep === lastAnnounced.current) return;
    lastAnnounced.current = currentStep;
    speakAlert(currentStep.instruction);
  }, [currentStep, enabled]);

  useEffect(() => {
    if (!enabled) lastAnnounced.current = null;
  }, [enabled]);
}
