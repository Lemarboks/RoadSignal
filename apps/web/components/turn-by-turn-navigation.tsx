"use client";

import { useState } from "react";
import type { RouteManeuver, RouteOption } from "@roadsignal/types";
import { RouteMap as MapView } from "./route-map";
import { formatStepDistance, turnByTurnState } from "../lib/turn-by-turn";
import { formatDistanceKm, loadPreferences } from "../lib/preferences";
import { useTurnAnnouncements } from "../features/trips/use-turn-announcements";

const TURN_ROTATION: Partial<Record<RouteManeuver, number>> = {
  straight: 0,
  "slight-right": 45,
  "turn-right": 90,
  "sharp-right": 135,
  uturn: 180,
  "sharp-left": -135,
  "turn-left": -90,
  "slight-left": -45,
};

function TurnIcon({ maneuver }: { maneuver: RouteManeuver }) {
  if (maneuver === "depart") {
    return (
      <svg width="34" height="34" viewBox="0 0 24 24" fill="none" aria-hidden="true">
        <circle cx="12" cy="12" r="7" fill="currentColor" />
      </svg>
    );
  }
  if (maneuver === "arrive") {
    return (
      <svg width="34" height="34" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
        <path d="M6 3v18" strokeLinecap="round" />
        <path d="M6 4h11l-3 3.5L17 11H6" strokeLinejoin="round" />
      </svg>
    );
  }
  if (maneuver === "roundabout") {
    return (
      <svg width="34" height="34" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
        <circle cx="12" cy="12" r="7" />
        <path d="M12 3v6l4-2" strokeLinecap="round" strokeLinejoin="round" />
      </svg>
    );
  }
  const rotation = TURN_ROTATION[maneuver] ?? 0;
  return (
    <svg
      width="34"
      height="34"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2.4"
      style={{ transform: `rotate(${rotation}deg)` }}
      aria-hidden="true"
    >
      <path d="M12 20V6" strokeLinecap="round" />
      <path d="M6 11l6-6 6 6" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

function CloseIcon() {
  return (
    <svg width="20" height="20" viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" aria-hidden="true">
      <path d="M4 4l12 12M16 4L4 16" />
    </svg>
  );
}

function SpeakerIcon({ muted }: { muted: boolean }) {
  return (
    <svg width="20" height="20" viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d="M3 8v4h3l4 3V5L6 8z" />
      {!muted && <path d="M13.5 7.5a3.5 3.5 0 0 1 0 5" />}
      {!muted && <path d="M15.5 5.5a6.5 6.5 0 0 1 0 9" />}
      {muted && <path d="M13 8l4 4M17 8l-4 4" />}
    </svg>
  );
}

export function TurnByTurnNavigation({
  route,
  progress,
  voiceEnabled,
  onToggleVoice,
  onClose,
}: {
  route: RouteOption;
  progress: number;
  voiceEnabled: boolean;
  onToggleVoice: () => void;
  onClose: () => void;
}) {
  const [unit] = useState(() => loadPreferences().distanceUnit);
  const state = turnByTurnState(route.steps, progress, route.distanceKm, route.durationMinutes);
  useTurnAnnouncements(state.currentStep, voiceEnabled);
  const maneuver = state.currentStep?.maneuver ?? "straight";

  return (
    <div className="turn-nav" role="dialog" aria-label="Turn-by-turn navigation" aria-modal="true">
      <header className="turn-nav-banner">
        <TurnIcon maneuver={maneuver} />
        <div>
          <strong>
            {state.currentStep?.instruction ?? `Following ${route.name}`}
          </strong>
          {state.currentStep && state.currentStep.maneuver !== "arrive" && (
            <span>{formatStepDistance(state.distanceToNextStepMeters, unit)}</span>
          )}
        </div>
      </header>
      <div className="turn-nav-map">
        <MapView routes={[route]} selected={route.id} progress={progress} />
      </div>
      <footer className="turn-nav-bar">
        <button type="button" className="turn-nav-close" onClick={onClose} aria-label="Exit turn-by-turn navigation">
          <CloseIcon />
        </button>
        <div className="turn-nav-summary">
          <strong>{state.remainingMinutes} min</strong>
          <span>{formatDistanceKm(state.remainingDistanceKm, unit)}</span>
        </div>
        <button
          type="button"
          className="turn-nav-voice"
          aria-pressed={voiceEnabled}
          aria-label={voiceEnabled ? "Mute voice guidance" : "Unmute voice guidance"}
          onClick={onToggleVoice}
        >
          <SpeakerIcon muted={!voiceEnabled} />
        </button>
      </footer>
    </div>
  );
}
