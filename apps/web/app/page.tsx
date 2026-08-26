"use client";
import { useEffect } from "react";
import { navIcons } from "../components/nav-icons";
import { BrandMark } from "../components/brand-mark";
import { EntryGate } from "../components/entry-gate";
import { defaultDestination, defaultOrigin } from "../features/demo-data";
import {
  AnalyticsPage,
  EvidencePage,
  FleetPage,
  RiskMapPage,
} from "../features/operations/operations-pages";
import { DashboardPage } from "../features/dashboard/dashboard-page";
import { RoutePlannerPage } from "../features/planner/route-planner-page";
import { LiveTripPage } from "../features/trips/live-trip-page";
import { IncidentsPage } from "../features/incidents/incidents-page";
import {
  API,
  useRoadSignalController,
} from "../features/use-road-signal-controller";
const nav = [
  "Dashboard",
  "Route Planner",
  "Live Trips",
  "Incidents",
  "Risk Map",
  "Analytics",
  "Fleet",
  "Settings",
] as const;
export default function App() {
  const {
    page,
    setPage,
    routes,
    setRoutes,
    selected,
    setSelected,
    loading,
    locating,
    locationPermission,
    notice,
    setNotice,
    dataMode,
    weather,
    weatherStatus,
    realtimeStatus,
    backendStatus,
    apiClient,
    session,
    setSession,
    entered,
    setEntered,
    riskEvidence,
    riskEvidenceSource,
    fleetAnalytics,
    fleetAnalyticsSource,
    analyticsWindow,
    setAnalyticsWindow,
    fleetQuery,
    setFleetQuery,
    fleetStatus,
    setFleetStatus,
    trip,
    setTrip,
    incidents,
    origin,
    setOrigin,
    destination,
    setDestination,
    preference,
    setPreference,
    resolvedOrigin,
    setResolvedOrigin,
    resolvedDestination,
    setResolvedDestination,
    audit,
    setAudit,
    route,
    safestAlternative,
    visibleDrivers,
    enrichRoutesWithWeather,
    useCurrentLocation,
    findRoutes,
    useDemoRoutes,
    startTrip,
    inject,
    moderate,
  } = useRoadSignalController();
  useEffect(() => {
    window.scrollTo(0, 0);
    if (document.activeElement instanceof HTMLElement) {
      document.activeElement.blur();
    }
  }, [entered]);
  const showEntryGate = () => {
    setEntered(false);
  };
  const enterWorkspace = () => {
    setEntered(true);
  };
  const dashboard = (
    <DashboardPage
      incidents={incidents}
      routes={routes}
      selected={selected}
      trip={trip}
      onPlanRoute={() => setPage("Route Planner")}
    />
  );
  const planner = (
    <RoutePlannerPage
      routes={routes}
      selected={selected}
      route={route}
      loading={loading}
      locating={locating}
      locationPermission={locationPermission}
      origin={origin}
      destination={destination}
      resolvedOrigin={resolvedOrigin}
      resolvedDestination={resolvedDestination}
      preference={preference}
      weather={weather}
      weatherStatus={weatherStatus}
      onOriginChange={setOrigin}
      onDestinationChange={setDestination}
      onOriginResolved={setResolvedOrigin}
      onDestinationResolved={setResolvedDestination}
      onPreferenceChange={setPreference}
      onUseCurrentLocation={useCurrentLocation}
      onFindRoutes={() => void findRoutes()}
      onUseDemoRoutes={() => useDemoRoutes()}
      onRetryWeather={() =>
        void enrichRoutesWithWeather(
          routes,
          resolvedOrigin ?? defaultOrigin,
          resolvedDestination ?? defaultDestination,
        ).then(setRoutes)
      }
      onSelectRoute={setSelected}
      onStartTrip={() => void startTrip()}
    />
  );
  const live = (
    <LiveTripPage
      trip={trip}
      routes={routes}
      selected={selected}
      origin={resolvedOrigin?.displayName.split(",")[0] ?? origin}
      destination={
        resolvedDestination?.displayName.split(",")[0] ?? destination
      }
      audit={audit}
      safestAlternative={safestAlternative}
      onAcceptSaferRoute={(alternative) => {
        setSelected(alternative.id);
        setTrip((current) => ({
          ...current,
          score: alternative.safetyScore,
          alerts: [],
        }));
        setAudit((current) => [
          `Reroute accepted via ${alternative.name}`,
          ...current,
        ]);
      }}
      onTogglePause={() =>
        setTrip((current) => ({ ...current, paused: !current.paused }))
      }
      onSimulateIncident={inject}
      onEndTrip={() => {
        setTrip((current) => ({
          ...current,
          active: false,
          paused: true,
          progress: 100,
        }));
        setAudit((current) => [
          "Trip completed and history stored",
          ...current,
        ]);
      }}
    />
  );
  const incidentPage = (
    <IncidentsPage
      incidents={incidents}
      onReport={() => inject("Road closure")}
      onModerate={moderate}
    />
  );
  const riskMapPage = (
    <RiskMapPage
      routes={routes}
      selected={selected}
      route={route}
      tripProgress={trip.progress}
      onSelectRoute={setSelected}
      onNavigate={setPage}
    />
  );
  const analyticsPage = (
    <AnalyticsPage
      analytics={fleetAnalytics}
      source={fleetAnalyticsSource}
      window={analyticsWindow}
      onWindowChange={setAnalyticsWindow}
      onOpenFleetQueue={() => {
        setFleetStatus("Attention");
        setPage("Fleet");
      }}
    />
  );
  const fleetPage = (
    <FleetPage
      query={fleetQuery}
      status={fleetStatus}
      visibleDrivers={visibleDrivers}
      onQueryChange={setFleetQuery}
      onStatusChange={setFleetStatus}
      onNavigate={setPage}
      onViewTrip={(driverName) => {
        setNotice(`Opening ${driverName}'s latest trip view.`);
        setPage("Live Trips");
      }}
    />
  );
  const evidencePage = (
    <EvidencePage evidence={riskEvidence} source={riskEvidenceSource} />
  );
  const pageContent = {
    Dashboard: dashboard,
    "Route Planner": planner,
    "Live Trips": live,
    Incidents: incidentPage,
    "Risk Map": riskMapPage,
    Analytics: analyticsPage,
    Fleet: fleetPage,
    Settings: evidencePage,
  }[page];
  if (!entered) {
    return (
      <EntryGate
        client={apiClient}
        onSession={(next) => {
          setSession(next);
          enterWorkspace();
        }}
        onGuest={enterWorkspace}
      />
    );
  }
  return (
    <>
      <a className="skip-link" href="#main-content">
        Skip to main content
      </a>
      <div className="shell">
        <aside aria-label="RoadSignal navigation">
          <div className="brand">
            <BrandMark className="brand-mark" />
            <span>
              RoadSignal
              <small>Route-risk intelligence</small>
            </span>
          </div>
          <nav aria-label="Application sections">
            {nav.map((n) => (
              <button
                className={page === n ? "active" : ""}
                onClick={() => setPage(n)}
                key={n}
                type="button"
                aria-current={page === n ? "page" : undefined}
              >
                <i aria-hidden="true">{navIcons[n as keyof typeof navIcons]}</i>
                {n}
                {n === "Incidents" && <em>{incidents.length}</em>}
              </button>
            ))}
          </nav>
          <div className={`account-dock ${session ? "signed-in" : "guest"}`}>
            {session ? (
              <>
                <span className="account-avatar" aria-hidden="true">
                  {session.user.name.slice(0, 2).toUpperCase()}
                </span>
                <span className="account-identity">
                  <strong>{session.user.name}</strong>
                  <small>{session.user.role.replaceAll("_", " ")}</small>
                </span>
                <button
                  type="button"
                  onClick={() => {
                    void apiClient.logout();
                    setSession(null);
                    showEntryGate();
                  }}
                >
                  Sign out
                </button>
              </>
            ) : (
              <button type="button" onClick={showEntryGate}>
                Sign in
              </button>
            )}
          </div>
        </aside>
        <main id="main-content" tabIndex={-1}>
          <section className="demo-banner" aria-label="Demonstration status">
            <div>
              <strong>GitHub Pages demonstration</strong>
              <span>
                This showcase uses{" "}
                {dataMode === "public"
                  ? "public map and road services"
                  : dataMode === "api"
                    ? "the configured API"
                    : "built-in simulated data"}
                . It is decision support, not a guarantee of safety.
              </span>
            </div>
            <div className="connection-badges" aria-live="polite">
              <span className={`mode-badge ${dataMode}`}>
                {dataMode === "public"
                  ? "Public data"
                  : dataMode === "api"
                    ? "API connected"
                    : "Demo data"}
              </span>
              {API && (
                <span className={`realtime-badge ${realtimeStatus}`}>
                  Realtime: {realtimeStatus}
                </span>
              )}
              {API && backendStatus === "waking" && (
                <span className="realtime-badge connecting">
                  Backend: waking up (can take up to a minute)
                </span>
              )}
              {API && backendStatus === "unavailable" && (
                <span className="realtime-badge disconnected">
                  Backend: unavailable, using public/demo data
                </span>
              )}
            </div>
          </section>
          {notice && (
            <div className="toast" role="status" aria-live="polite">
              <span>{notice}</span>
              <button
                type="button"
                onClick={() => setNotice("")}
                aria-label="Dismiss notification"
              >
                Close
              </button>
            </div>
          )}
          {pageContent}
        </main>
      </div>
    </>
  );
}
