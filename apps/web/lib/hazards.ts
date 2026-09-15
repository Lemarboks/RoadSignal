export type WildfireHotspot = {
  latitude: number;
  longitude: number;
  frp: number;
  confidence: string;
  acquired_at: string;
};
export type WildfireHotspots = { hotspots: WildfireHotspot[]; source: string; count: number };

export type SevereWeatherEvent = {
  id: string;
  title: string;
  category: "floods" | "landslides" | "severeStorms" | "dustHaze" | "snow" | "tempExtremes";
  latitude: number;
  longitude: number;
};
export type SevereWeatherEvents = { events: SevereWeatherEvent[]; source: string; count: number };

export type CctvCamera = {
  id: string;
  name: string;
  latitude: number;
  longitude: number;
  feed_url: string;
  feed_type: "image" | "m3u8" | string;
  source: string;
};
export type CctvCameras = { cameras: CctvCamera[]; source: string; count: number };

export type HazardLayerState<T> = { data: T[]; status: "loading" | "ready" | "unavailable" };

export const SEVERE_WEATHER_LABELS: Record<SevereWeatherEvent["category"], string> = {
  floods: "Flooding",
  landslides: "Landslide risk",
  severeStorms: "Severe storm",
  dustHaze: "Dust / haze",
  snow: "Snow event",
  tempExtremes: "Extreme temperature",
};
