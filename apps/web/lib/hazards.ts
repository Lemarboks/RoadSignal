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

// Open municipal faults, fetched live rather than shipped: a street light
// reported out only matters while it is still out.
export type ServiceRequestCategory = "street_light" | "traffic_signal" | "road_water";
export type ServiceRequest = {
  id: string;
  category: ServiceRequestCategory;
  label: string;
  complaint_type: string;
  suburb: string | null;
  latitude: number;
  longitude: number;
  reported_at: string | null;
};
export type ServiceRequests = {
  requests: ServiceRequest[];
  count: number;
  by_category: Partial<Record<ServiceRequestCategory, number>>;
  labels: Record<ServiceRequestCategory, string>;
  window_days: number;
  source: string;
  status?: HazardSourceStatus;
  detail?: string | null;
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
