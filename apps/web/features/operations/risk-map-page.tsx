import type { RouteOption } from "@roadsignal/types";
import { RouteMap as MapView } from "../../components/route-map";
import { demoRiskZones } from "../demo-data";
import type { AppPage } from "./operations-pages";

const riskClass = (score: number) => score >= 80 ? "low" : score >= 60 ? "medium" : "high";
type Navigate = (page: AppPage) => void;

export function RiskMapPage({
  routes,
  selected,
  route,
  tripProgress,
  onSelectRoute,
  onNavigate,
}: {
  routes: RouteOption[];
  selected: string;
  route: RouteOption;
  tripProgress: number;
  onSelectRoute: (routeId: string) => void;
  onNavigate: Navigate;
}) {
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
          />
        </section>
        <section className="risk-zone-rail" aria-labelledby="risk-zone-title">
          <div className="section-heading-row">
            <div>
              <h2 id="risk-zone-title">Areas to review</h2>
              <p>Ranked demonstration signals</p>
            </div>
          </div>
          <ol className="risk-zone-list">
            {demoRiskZones.map((zone) => (
              <li key={zone.area}>
                <div>
                  <strong>{zone.area}</strong>
                  <span>{zone.signal}</span>
                </div>
                <div className="zone-reading">
                  <b className={zone.level.toLowerCase()}>{zone.level}</b>
                  <span>
                    {zone.score}/100 · {zone.confidence}
                  </span>
                </div>
              </li>
            ))}
          </ol>
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
        Risk areas and scores are demonstration estimates, not guarantees of
        personal safety.
      </p>
    </>
  );
}
