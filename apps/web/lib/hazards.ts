export type WildfireHotspot = {
  latitude: number;
  longitude: number;
  frp: number;
  confidence: string;
  acquired_at: string;
};
export type HazardSourceStatus = "ok" | "unavailable";
export type WildfireHotspots = { hotspots: WildfireHotspot[]; source: string; count: number; status?: HazardSourceStatus; detail?: string | null };

export type SevereWeatherEvent = {
  id: string;
  title: string;
  category: "floods" | "landslides" | "severeStorms" | "dustHaze" | "snow" | "tempExtremes";
  latitude: number;
  longitude: number;
};
export type SevereWeatherEvents = { events: SevereWeatherEvent[]; source: string; count: number; status?: HazardSourceStatus; detail?: string | null };

export type CctvCamera = {
  id: string;
  name: string;
  latitude: number;
  longitude: number;
  feed_url: string;
  feed_type: "image" | "m3u8" | string;
  source: string;
};
export type CctvCameras = { cameras: CctvCamera[]; source: string; count: number; status?: HazardSourceStatus; detail?: string | null };

export type CrimePrecinct = {
  code: string;
  name: string;
  rings: number[][][];
  per_km2: number;
  rate_per_100k: number;
  percentile: number;
  crime_baseline: number;
  weighted_incidents: number;
  breakdown: Record<string, number>;
  population: number;
  area_km2: number;
};
export type CrimePrecincts = {
  precincts: CrimePrecinct[];
  count: number;
  source: string;
  municipality: string;
  window: string;
  categories: string[];
};

// Recorded crash history per precinct. Shares the crime layer's boundaries and
// percentile scale, so one map source can render either metric.
export type CrashPrecinct = {
  code: string;
  name: string;
  rings: number[][][];
  crashes: number;
  fatal: number;
  serious: number;
  pedestrians: number;
  percentile: number;
  accident_baseline: number;
};
export type CrashHistory = {
  precincts: CrashPrecinct[];
  count: number;
  available: boolean;
  source: string;
  source_terms?: string;
  window: string;
  crashes: number;
};

export type HazardLayerState<T> = { data: T[]; status: "loading" | "ready" | "unavailable" };

export const SEVERE_WEATHER_LABELS: Record<SevereWeatherEvent["category"], string> = {
  floods: "Flooding",
  landslides: "Landslide risk",
  severeStorms: "Severe storm",
  dustHaze: "Dust / haze",
  snow: "Snow event",
  tempExtremes: "Extreme temperature",
};
