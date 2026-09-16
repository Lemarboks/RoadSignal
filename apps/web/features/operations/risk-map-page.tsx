import type { Incident, RouteOption } from "@roadsignal/types";
import { RouteMap as MapView, type HazardLayers } from "../../components/route-map";
import type { RouteWeather } from "../../lib/open-weather";
import type { MapCellsState } from "../../lib/map-cells";
import { topRiskAreas } from "../../lib/risk-areas";
import type { AppPage } from "./operations-pages";

const riskClass = (score: number) => score >= 80 ? "low" : score >= 60 ? "medium" : "high";
type Navigate = (page: AppPage) => void;

export function RiskMapPage({
  routes,
  selected,
  route,
  tripProgress,
  weather,
  weatherStatus,
  incidents,
  onSelectRoute,
  onNavigate,
  cells,
  hazards,
}: {
  routes: RouteOption[];
  selected: string;
  route: RouteOption;
  tripProgress: number;
  weather: RouteWeather | null;
  weatherStatus: "loading" | "ready" | "unavailable";
  incidents: Incident[];
  onSelectRoute: (routeId: string) => void;
  onNavigate: Navigate;
  cells: MapCellsState;
  hazards?: HazardLayers;
}) {
  // Real reported figures replace what used to be a hardcoded list of
  // invented zones. No fallback to demo values: invented numbers here would
  // be indistinguishable from measured ones.
  const riskAreas = topRiskAreas(hazards?.crimePrecincts?.data ?? []);
  const crimeWindow = hazards?.crimeMeta?.window ?? "";
  const crimeStatus = hazards?.crimePrecincts?.status ?? "unavailable";
  return (
    <>
      <section className="heading risk-map-heading">
        <div>
          <p className="eyebrow">Live network exposure</p>
          <h1>Network risk map</h1>
          <p>
            Inspect route corridors and prioritise areas that need operational
            attention.
          </p>
        </div>
        <button
          type="button"
          className="primary"
          onClick={() => onNavigate("Incidents")}
        >
          Review incidents
        </button>
      </section>
      <div className="risk-map-toolbar" aria-label="Route layer selection">
        <span>Route layer</span>
        <div className="segmented-control">
          {routes.map((candidate) => (
            <button
              type="button"
              key={candidate.id}
              aria-pressed={selected === candidate.id}
              onClick={() => onSelectRoute(candidate.id)}
            >
              {candidate.name}
            </button>
          ))}
        </div>
        <span className={`risk-map-score ${riskClass(route.safetyScore)}`}>
          {route.safetyScore}/100 estimate
        </span>
      </div>
      <div className="risk-map-layout">
        <section className="risk-map-stage" aria-labelledby="risk-map-title">
          <div className="section-heading-row">
            <div>
              <h2 id="risk-map-title">Cape Town route exposure</h2>
              <p>{route.explanation}</p>
            </div>
            <span>
              {route.confidence
                ? `${Math.round(route.confidence * 100)}% confidence`
                : "Confidence unavailable"}
            </span>
          </div>
          <MapView
            routes={routes}
            selected={selected}
            progress={tripProgress}
            weather={weather}
            weatherStatus={weatherStatus}
            incidents={incidents}
            onSelectRoute={onSelectRoute}
            cells={cells}
            hazards={hazards}
          />
        </section>
        <section className="risk-zone-rail" aria-labelledby="risk-zone-title">
          <div className="section-heading-row">
            <div>
              <h2 id="risk-zone-title">Areas to review</h2>
              <p>
                {riskAreas.length
                  ? `Highest reported vehicle crime${crimeWindow ? ` · ${crimeWindow}` : ""}`
                  : "Reported crime figures"}
              </p>
            </div>
          </div>
          {riskAreas.length ? (
            <ol className="risk-zone-list">
              {riskAreas.map((area) => (
                <li key={area.code}>
                  <div>
                    <strong>{area.name}</strong>
                    <span>
                      {area.topCategory
                        ? `${area.topCategory} · ${area.topCategoryCount} reported`
                        : "No vehicle crime reported"}
                    </span>
                  </div>
                  <div className="zone-reading">
                    <b className={area.level.toLowerCase()}>{area.level}</b>
                    <span>
                      {area.perKm2}/km&sup2; · {area.areaKm2} km&sup2;
                    </span>
                  </div>
                </li>
              ))}
            </ol>
          ) : (
            <p className="empty risk-zone-empty">
              {crimeStatus === "loading"
                ? "Loading reported crime figures…"
                : "Reported crime figures are unavailable. Connect the service to load them."}
            </p>
          )}
          <button
            type="button"
            className="rail-action"
            onClick={() => onNavigate("Route Planner")}
          >
            Plan around these signals
          </button>
        </section>
      </div>
      <p className="view-disclaimer">
        {riskAreas.length
          ? "Areas to review show reported crime counts published by SAPS. Route safety scores are decision-support estimates, not guarantees of personal safety."
          : "Route safety scores are decision-support estimates, not guarantees of personal safety."}
      </p>
    </>
  );
}
