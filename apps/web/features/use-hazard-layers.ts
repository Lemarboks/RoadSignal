import { useEffect, useState } from "react";
import type { RoadSignalApiClient } from "../lib/api-client";
import { assistantRequest } from "../lib/assistant";
import type {
  CctvCamera,
  CctvCameras,
  CrashHistory,
  CrashPrecinct,
  CrimePrecinct,
  CrimePrecincts,
  HazardLayerState,
  ServiceRequest,
  ServiceRequests,
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
  const [crashPrecincts, setCrashPrecincts] = useState<HazardLayerState<CrashPrecinct>>(enabled ? LOADING : UNAVAILABLE);
  const [crashMeta, setCrashMeta] = useState<{ window: string; source: string; crashes: number } | null>(null);
  const [serviceRequests, setServiceRequests] = useState<HazardLayerState<ServiceRequest>>(enabled ? LOADING : UNAVAILABLE);
  const [serviceMeta, setServiceMeta] = useState<{ source: string; windowDays: number } | null>(null);

  useEffect(() => {
    if (!enabled) return;
    const controller = new AbortController();
    setWildfires(LOADING);
    void assistantRequest<WildfireHotspots>(client, "/api/v1/hazards/wildfires", { signal: controller.signal }, 15_000)
      // A reachable feed reporting zero hotspots is "ready"; a feed that could
      // not be reached is "unavailable". Both used to arrive as count: 0.
      .then((body) => { if (!controller.signal.aborted) setWildfires({ data: body.hotspots, status: body.status === "unavailable" ? "unavailable" : "ready" }); })
      .catch(() => { if (!controller.signal.aborted) setWildfires(UNAVAILABLE); });
    return () => controller.abort();
  }, [client, enabled]);

  useEffect(() => {
    if (!enabled) return;
    const controller = new AbortController();
    setSevereWeather(LOADING);
    void assistantRequest<SevereWeatherEvents>(client, "/api/v1/hazards/severe-weather", { signal: controller.signal }, 15_000)
      .then((body) => { if (!controller.signal.aborted) setSevereWeather({ data: body.events, status: body.status === "unavailable" ? "unavailable" : "ready" }); })
      .catch(() => { if (!controller.signal.aborted) setSevereWeather(UNAVAILABLE); });
    return () => controller.abort();
  }, [client, enabled]);

  useEffect(() => {
    if (!enabled) return;
    const controller = new AbortController();
    setCameras(LOADING);
    void assistantRequest<CctvCameras>(client, "/api/v1/hazards/cameras", { signal: controller.signal }, 15_000)
      .then((body) => { if (!controller.signal.aborted) setCameras({ data: body.cameras, status: body.status === "unavailable" ? "unavailable" : "ready" }); })
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

  useEffect(() => {
    if (!enabled) return;
    const controller = new AbortController();
    setCrashPrecincts(LOADING);
    void assistantRequest<CrashHistory>(client, "/api/v1/hazards/crash-history", { signal: controller.signal }, 15_000)
      .then((body) => {
        if (controller.signal.aborted) return;
        // available:false means the dataset is missing, not that Cape Town has
        // no crashes -- report it unavailable rather than as an empty layer.
        setCrashPrecincts({ data: body.precincts ?? [], status: body.available === false ? "unavailable" : "ready" });
        setCrashMeta({ window: body.window, source: body.source, crashes: body.crashes });
      })
      .catch(() => { if (!controller.signal.aborted) setCrashPrecincts(UNAVAILABLE); });
    return () => controller.abort();
  }, [client, enabled]);

  useEffect(() => {
    if (!enabled) return;
    const controller = new AbortController();
    setServiceRequests(LOADING);
    void assistantRequest<ServiceRequests>(client, "/api/v1/hazards/service-requests", { signal: controller.signal }, 20_000)
      .then((body) => {
        if (controller.signal.aborted) return;
        setServiceRequests({ data: body.requests ?? [], status: body.status === "unavailable" ? "unavailable" : "ready" });
        setServiceMeta({ source: body.source, windowDays: body.window_days });
      })
      .catch(() => { if (!controller.signal.aborted) setServiceRequests(UNAVAILABLE); });
    return () => controller.abort();
  }, [client, enabled]);

  return { wildfires, severeWeather, cameras, crimePrecincts, crimeMeta, crashPrecincts, crashMeta, serviceRequests, serviceMeta };
}
