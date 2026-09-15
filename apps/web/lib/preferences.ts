export type ThemePreference = "system" | "light" | "dark";
export type DistanceUnit = "km" | "mi";
export type VoiceEngine = "browser" | "voicebox";

export type Preferences = {
  theme: ThemePreference;
  voiceAlertsDefault: boolean;
  distanceUnit: DistanceUnit;
  voiceEngine: VoiceEngine;
  voiceboxUrl: string;
  voiceboxProfileId: string;
};

export const DEFAULT_VOICEBOX_URL = "http://127.0.0.1:17493";

export const DEFAULT_PREFERENCES: Preferences = {
  theme: "system",
  voiceAlertsDefault: true,
  distanceUnit: "km",
  voiceEngine: "browser",
  voiceboxUrl: DEFAULT_VOICEBOX_URL,
  voiceboxProfileId: "",
};

const STORAGE_KEY = "roadsignal:preferences";

export function loadPreferences(): Preferences {
  if (typeof window === "undefined") return DEFAULT_PREFERENCES;
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return DEFAULT_PREFERENCES;
    const parsed = JSON.parse(raw) as Partial<Preferences>;
    return {
      theme: parsed.theme === "light" || parsed.theme === "dark" ? parsed.theme : "system",
      voiceAlertsDefault: typeof parsed.voiceAlertsDefault === "boolean" ? parsed.voiceAlertsDefault : true,
      distanceUnit: parsed.distanceUnit === "mi" ? "mi" : "km",
      voiceEngine: parsed.voiceEngine === "voicebox" ? "voicebox" : "browser",
      voiceboxUrl: typeof parsed.voiceboxUrl === "string" && parsed.voiceboxUrl.trim() ? parsed.voiceboxUrl : DEFAULT_VOICEBOX_URL,
      voiceboxProfileId: typeof parsed.voiceboxProfileId === "string" ? parsed.voiceboxProfileId : "",
    };
  } catch {
    return DEFAULT_PREFERENCES;
  }
}

export function savePreferences(preferences: Preferences) {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(preferences));
  } catch {
    // Storage can be unavailable in privacy mode; preferences just won't persist.
  }
}

export function applyTheme(theme: ThemePreference) {
  if (typeof document === "undefined") return;
  if (theme === "system") delete document.documentElement.dataset.theme;
  else document.documentElement.dataset.theme = theme;
}

export function kilometersToMiles(km: number): number {
  return km * 0.621371;
}

export function formatDistanceKm(km: number, unit: DistanceUnit): string {
  const value = unit === "mi" ? kilometersToMiles(km) : km;
  const rounded = value < 10 ? Math.round(value * 10) / 10 : Math.round(value);
  return `${rounded} ${unit}`;
}
