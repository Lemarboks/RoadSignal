import { useEffect, useState } from "react";
import type { RoadSignalApiClient } from "../lib/api-client";
import { assistantRequest } from "../lib/assistant";
import type {
  CctvCamera,
  CctvCameras,
  CrimePrecinct,
  CrimePrecincts,
  HazardLayerState,
  SevereWeatherEvent,
  SevereWeatherEvents,
  WildfireHotspot,
  WildfireHotspots,
} from "../lib/hazards";

const LOADING = { data: [], status: "loading" as const };
const UNAVAILABLE = { data: [], status: "unavailable" as const };

export function useHazardLayers(client: RoadSignalApiClient, enabled: boolean) {
  const [wildfires, setWildfires] = useState<HazardLayerState<WildfireHotspot>>(enabled ? LOADING : UNAVAILABLE);
  const [severeWeather, setSevereWeather] = useState<HazardLayerState<SevereWeatherEvent>>(enabled ? LOADING : UNAVAILABLE);
  const [cameras, setCameras] = useState<HazardLayerState<CctvCamera>>(enabled ? LOADING : UNAVAILABLE);
  const [crimePrecincts, setCrimePrecincts] = useState<HazardLayerState<CrimePrecinct>>(enabled ? LOADING : UNAVAILABLE);
  const [crimeMeta, setCrimeMeta] = useState<{ window: string; source: string } | null>(null);

  useEffect(() => {
    if (!enabled) return;
    const controller = new AbortController();
    setWildfires(LOADING);
    void assistantRequest<WildfireHotspots>(client, "/api/v1/hazards/wildfires", { signal: controller.signal }, 15_000)
      .then((body) => { if (!controller.signal.aborted) setWildfires({ data: body.hotspots, status: "ready" }); })
      .catch(() => { if (!controller.signal.aborted) setWildfires(UNAVAILABLE); });
    return () => controller.abort();
  }, [client, enabled]);

  useEffect(() => {
    if (!enabled) return;
    const controller = new AbortController();
    setSevereWeather(LOADING);
    void assistantRequest<SevereWeatherEvents>(client, "/api/v1/hazards/severe-weather", { signal: controller.signal }, 15_000)
      .then((body) => { if (!controller.signal.aborted) setSevereWeather({ data: body.events, status: "ready" }); })
      .catch(() => { if (!controller.signal.aborted) setSevereWeather(UNAVAILABLE); });
    return () => controller.abort();
  }, [client, enabled]);

  useEffect(() => {
    if (!enabled) return;
    const controller = new AbortController();
    setCameras(LOADING);
    void assistantRequest<CctvCameras>(client, "/api/v1/hazards/cameras", { signal: controller.signal }, 15_000)
      .then((body) => { if (!controller.signal.aborted) setCameras({ data: body.cameras, status: "ready" }); })
      .catch(() => { if (!controller.signal.aborted) setCameras(UNAVAILABLE); });
    return () => controller.abort();
  }, [client, enabled]);

  useEffect(() => {
    if (!enabled) return;
    const controller = new AbortController();
    setCrimePrecincts(LOADING);
    void assistantRequest<CrimePrecincts>(client, "/api/v1/hazards/crime-precincts", { signal: controller.signal }, 15_000)
      .then((body) => {
        if (controller.signal.aborted) return;
        setCrimePrecincts({ data: body.precincts, status: "ready" });
        setCrimeMeta({ window: body.window, source: body.source });
      })
      .catch(() => { if (!controller.signal.aborted) setCrimePrecincts(UNAVAILABLE); });
    return () => controller.abort();
  }, [client, enabled]);

  return { wildfires, severeWeather, cameras, crimePrecincts, crimeMeta };
}
