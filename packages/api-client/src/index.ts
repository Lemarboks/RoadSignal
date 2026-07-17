import type { Incident, RouteOption, RoutePreference, Trip } from "@saferoute/types";

export class SafeRouteClient {
  constructor(private readonly baseUrl = "http://localhost:8000") {}
  private async request<T>(path: string, init?: RequestInit): Promise<T> {
    const response = await fetch(`${this.baseUrl}${path}`, { ...init, headers: { "Content-Type": "application/json", ...init?.headers } });
    if (!response.ok) throw new Error((await response.json().catch(() => null))?.detail ?? `Request failed (${response.status})`);
    return response.json() as Promise<T>;
  }
  analyseRoutes(origin: string, destination: string, preference: RoutePreference = "balanced") {
    return this.request<{ routes: RouteOption[] }>("/api/v1/routes/analyse", { method: "POST", body: JSON.stringify({ origin, destination, preference, departure_time: new Date().toISOString(), vehicle_type: "car" }) });
  }
  listIncidents() { return this.request<{ items: Incident[] }>("/api/v1/incidents"); }
  createIncident(body: Record<string, unknown>) { return this.request<Incident>("/api/v1/incidents", { method: "POST", body: JSON.stringify(body) }); }
  moderateIncident(id: string, action: "confirm" | "dispute" | "resolve") { return this.request<Incident>(`/api/v1/incidents/${id}/${action}`, { method: "POST" }); }
  startTrip(routeId: string) { return this.request<Trip>(`/api/v1/routes/${routeId}/start`, { method: "POST" }); }
}
