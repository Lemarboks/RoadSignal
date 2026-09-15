import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import {
  DEFAULT_PREFERENCES,
  DEFAULT_VOICEBOX_URL,
  formatDistanceKm,
  kilometersToMiles,
  loadPreferences,
  savePreferences,
} from "./preferences";

function fakeStorage() {
  const store = new Map<string, string>();
  return {
    getItem: (key: string) => store.get(key) ?? null,
    setItem: (key: string, value: string) => void store.set(key, value),
    removeItem: (key: string) => void store.delete(key),
    clear: () => store.clear(),
  };
}

beforeEach(() => {
  vi.stubGlobal("window", { localStorage: fakeStorage() });
  vi.stubGlobal("localStorage", (window as unknown as { localStorage: Storage }).localStorage);
});
afterEach(() => vi.unstubAllGlobals());

describe("loadPreferences", () => {
  it("returns the defaults when nothing is stored", () => {
    expect(loadPreferences()).toEqual(DEFAULT_PREFERENCES);
  });

  it("round-trips a full preferences object through save/load", () => {
    savePreferences({
      theme: "dark",
      voiceAlertsDefault: false,
      distanceUnit: "mi",
      voiceEngine: "voicebox",
      voiceboxUrl: "http://192.168.1.5:17493",
      voiceboxProfileId: "profile-1",
    });
    expect(loadPreferences()).toEqual({
      theme: "dark",
      voiceAlertsDefault: false,
      distanceUnit: "mi",
      voiceEngine: "voicebox",
      voiceboxUrl: "http://192.168.1.5:17493",
      voiceboxProfileId: "profile-1",
    });
  });

  it("falls back to defaults for invalid or missing fields", () => {
    localStorage.setItem(
      "roadsignal:preferences",
      JSON.stringify({ theme: "purple", distanceUnit: "furlongs", voiceboxUrl: "" }),
    );
    const preferences = loadPreferences();
    expect(preferences.theme).toBe("system");
    expect(preferences.distanceUnit).toBe("km");
    expect(preferences.voiceboxUrl).toBe(DEFAULT_VOICEBOX_URL);
    expect(preferences.voiceEngine).toBe("browser");
  });

  it("recovers from corrupt stored JSON", () => {
    localStorage.setItem("roadsignal:preferences", "{not json");
    expect(loadPreferences()).toEqual(DEFAULT_PREFERENCES);
  });
});

describe("kilometersToMiles / formatDistanceKm", () => {
  it("converts kilometres to miles", () => {
    expect(kilometersToMiles(10)).toBeCloseTo(6.21371, 4);
  });

  it("formats in kilometres by default", () => {
    expect(formatDistanceKm(8.2, "km")).toBe("8.2 km");
    expect(formatDistanceKm(24, "km")).toBe("24 km");
  });

  it("formats in miles when requested", () => {
    expect(formatDistanceKm(16.09344, "mi")).toBe("10 mi");
  });
});
