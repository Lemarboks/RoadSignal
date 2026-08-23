import type { RouteOption, RoutePreference } from "@roadsignal/types";
import { Metric } from "../../components/metric";
import { PlaceSearch } from "../../components/place-search";
import { RouteMap as MapView } from "../../components/route-map";
import type { ResolvedPlace } from "../../lib/open-routing";
import type { RouteWeather } from "../../lib/open-weather";

type LocationPermission =
  | "checking"
  | "prompt"
  | "granted"
  | "denied"
  | "unsupported";

const riskClass = (score: number) =>
  score >= 80 ? "low" : score >= 60 ? "medium" : "high";

export function RoutePlannerPage({
  routes,
  selected,
  route,
  loading,
  locating,
  locationPermission,
  origin,
  destination,
  resolvedOrigin,
  resolvedDestination,
  preference,
  weather,
  weatherStatus,
  onOriginChange,
  onDestinationChange,
  onOriginResolved,
  onDestinationResolved,
  onPreferenceChange,
  onUseCurrentLocation,
  onFindRoutes,
  onUseDemoRoutes,
  onRetryWeather,
  onSelectRoute,
  onStartTrip,
}: {
  routes: RouteOption[];
  selected: string;
  route: RouteOption;
  loading: boolean;
  locating: boolean;
  locationPermission: LocationPermission;
  origin: string;
  destination: string;
  resolvedOrigin: ResolvedPlace | null;
  resolvedDestination: ResolvedPlace | null;
  preference: RoutePreference;
  weather: RouteWeather | null;
  weatherStatus: "loading" | "ready" | "unavailable";
  onOriginChange: (value: string) => void;
  onDestinationChange: (value: string) => void;
  onOriginResolved: (place: ResolvedPlace | null) => void;
  onDestinationResolved: (place: ResolvedPlace | null) => void;
  onPreferenceChange: (preference: RoutePreference) => void;
  onUseCurrentLocation: () => void;
  onFindRoutes: () => void;
  onUseDemoRoutes: () => void;
  onRetryWeather: () => void;
  onSelectRoute: (routeId: string) => void;
  onStartTrip: () => void;
}) {
  const permissionTitle =
    locationPermission === "granted"
      ? "Location access enabled"
      : locationPermission === "denied"
        ? "Location access blocked"
        : locationPermission === "unsupported"
          ? "Location unavailable"
          : "Enable current location";
  const permissionCopy =
    locationPermission === "granted"
      ? "Your browser can use your position as the route origin."
      : locationPermission === "denied"
        ? "Allow location in browser settings, or search manually."
        : locationPermission === "unsupported"
          ? "This browser does not expose geolocation; manual search still works."
          : "Permission is requested only when you press Enable.";
  return (
    <>
      <section className="heading">
        <div>
          <p className="eyebrow">Route intelligence</p>
          <h1>Route Planner</h1>
          <p>Compare travel time against confidence-weighted route risk.</p>
        </div>
      </section>
      <div className="planner">
        <section className="panel controls">
          <div
            className={`location-permission ${locationPermission}`}
            aria-live="polite"
          >
            <div>
              <strong>{permissionTitle}</strong>
              <span>{permissionCopy}</span>
            </div>
            {locationPermission !== "granted" &&
              locationPermission !== "unsupported" && (
                <button
                  type="button"
                  onClick={onUseCurrentLocation}
                  disabled={locating || locationPermission === "checking"}
                >
                  {locating
                    ? "Locating..."
                    : locationPermission === "denied"
                      ? "Try again"
                      : "Enable"}
                </button>
              )}
          </div>
          <label>
            Origin
            <PlaceSearch
              value={origin}
              onChange={onOriginChange}
              resolved={resolvedOrigin}
              onResolved={onOriginResolved}
              placeholder="Street, landmark or suburb"
            />
            <button
              className="location-button"
              type="button"
              onClick={onUseCurrentLocation}
              disabled={locating}
            >
              {locating ? "Locating..." : "Use current location"}
            </button>
          </label>
          <label>
            Destination
            <PlaceSearch
              value={destination}
              onChange={onDestinationChange}
              resolved={resolvedDestination}
              onResolved={onDestinationResolved}
              placeholder="Street, landmark or suburb"
            />
          </label>
          <div className="row">
            <label>
              Departure
              <input type="datetime-local" defaultValue="2026-07-17T14:30" />
            </label>
            <label>
              Vehicle
              <select>
                <option>Car</option>
                <option>Motorcycle</option>
                <option>Van</option>
              </select>
            </label>
          </div>
          <label>
            Preference
            <select
              value={preference}
              onChange={(event) =>
                onPreferenceChange(event.target.value as RoutePreference)
              }
            >
              <option value="balanced">Balanced</option>
              <option value="safest">Safest</option>
              <option value="fastest">Fastest</option>
            </select>
          </label>
          <button
            type="button"
            className="primary wide"
            onClick={onFindRoutes}
            disabled={loading}
          >
            {loading ? "Resolving places and road routes..." : "Find routes"}
          </button>
          <button
            className="demo-route-button"
            type="button"
            onClick={onUseDemoRoutes}
          >
            Use built-in demo routes
          </button>
          <p className="routing-attribution">
            Search by{" "}
            <a href="https://photon.komoot.io" target="_blank" rel="noreferrer">
              Photon
            </a>
            {" - "}routing by{" "}
            <a
              href="https://routing.openstreetmap.de/about.html"
              target="_blank"
              rel="noreferrer"
            >
              OSRM/FOSSGIS
            </a>
            {" - "}
            <a
              href="https://www.openstreetmap.org/copyright"
              target="_blank"
              rel="noreferrer"
            >
              OpenStreetMap contributors
            </a>
          </p>
        </section>
        <MapView routes={routes} selected={selected} />
      </div>
      <section
        className={`weather-strip ${weatherStatus}`}
        aria-live="polite"
        aria-busy={weatherStatus === "loading"}
      >
        <div className="weather-heading">
          <span className="weather-symbol" aria-hidden="true">
            WX
          </span>
          <div>
            <h2>Route weather</h2>
            <p>Current conditions near the route corridor</p>
          </div>
        </div>
        {weatherStatus === "loading" ? (
          <p className="weather-message">Checking current conditions...</p>
        ) : weatherStatus === "unavailable" || !weather ? (
          <div className="weather-message">
            <span>
              Weather is temporarily unavailable. Route planning still works
              without it.
            </span>
            <button type="button" onClick={onRetryWeather}>
              Retry weather
            </button>
          </div>
        ) : (
          <>
            <dl className="weather-readings">
              <div>
                <dt>Conditions</dt>
                <dd>{weather.condition}</dd>
              </div>
              <div>
                <dt>Temperature</dt>
                <dd>{Math.round(weather.temperatureC)}&deg;C</dd>
              </div>
              <div>
                <dt>Feels like</dt>
                <dd>{Math.round(weather.apparentTemperatureC)}&deg;C</dd>
              </div>
              <div>
                <dt>Wind</dt>
                <dd>{Math.round(weather.windSpeedKmh)} km/h</dd>
              </div>
              <div>
                <dt>Visibility</dt>
                <dd>{weather.visibilityKm} km</dd>
              </div>
              <div>
                <dt>Weather risk</dt>
                <dd
                  className={`weather-risk ${weather.riskLabel.toLowerCase()}`}
                >
                  {weather.riskLabel}
                </dd>
              </div>
            </dl>
            <p className="weather-source">
              Live data by{" "}
              <a
                href="https://open-meteo.com/"
                target="_blank"
                rel="noreferrer"
              >
                Open-Meteo
              </a>
              . No API key, cookies, or precise device location is sent.
            </p>
          </>
        )}
      </section>
      <div className="route-grid">
        {routes.map((candidate) => (
          <button
            type="button"
            className={`route-card ${selected === candidate.id ? "selected" : ""}`}
            onClick={() => onSelectRoute(candidate.id)}
            key={candidate.id}
            aria-pressed={selected === candidate.id}
            aria-label={`${candidate.name}: ${candidate.durationMinutes} minutes, ${candidate.distanceKm} kilometres, safety estimate ${candidate.safetyScore} out of 100`}
          >
            {candidate.recommended && <em>Recommended</em>}
            <h3>{candidate.name}</h3>
            <div className="route-stats">
              <strong>{candidate.durationMinutes} min</strong>
              <span>{candidate.distanceKm} km</span>
            </div>
            <div className={`score ${riskClass(candidate.safetyScore)}`}>
              {candidate.safetyScore}
              <small>/100 safety</small>
            </div>
            <p>
              {candidate.differenceFromFastest
                ? `${candidate.differenceFromFastest} minutes slower than fastest`
                : "Fastest arrival"}
            </p>
            <div className="chips">
              {candidate.factors.map((factor) => (
                <span key={factor}>{factor}</span>
              ))}
            </div>
          </button>
        ))}
      </div>
      <section className="panel explanation">
        <h2>Why this route?</h2>
        <div className="risk-cols">
          <div>
            <div className={`big-score ${riskClass(route.safetyScore)}`}>
              {route.safetyScore}
            </div>
            <span>Overall safety estimate</span>
          </div>
          {Object.entries(route.breakdown).map(([key, value]) => (
            <Metric
              key={key}
              label={key.replace(/([A-Z])/g, " $1")}
              value={`${Math.round(100 - Number(value))}/100`}
            />
          ))}
        </div>
        <p>{route.explanation}</p>
        <p className="disclaimer">
          Safety scores are decision-support estimates based on available data.
          They do not measure or guarantee personal safety.
        </p>
        <button type="button" className="primary" onClick={onStartTrip}>
          Start simulated trip
        </button>
      </section>
    </>
  );
}
