"use client";
import { useCallback, useMemo, useState } from "react";
import { RouteMap } from "../../components/route-map";
import { ageLabel, REPLAY_SECONDS } from "../../lib/demo-telemetry";
import { demoDrivers, fallbackRoutes, type DemoDriver } from "../demo-data";
import { useDemoReplay } from "./use-demo-replay";
import type { RoadSignalApiClient, SessionSnapshot } from "../../lib/api-client";
import { timestampLabel } from "../../lib/connected-monitoring";
import { useConnectedMonitoring } from "./use-connected-monitoring";
import { MonitoringAutomation } from "./monitoring-automation";
import { deployment } from "../../lib/deployment";

/* Operate / local extension. THESIS: a controllable replay makes device state
   visible. OWN-WORLD: existing charcoal, signal yellow, semantic status colors.
   STORY: select a unit, inspect freshness, pause and compare sensor readings.
   FIRST VIEWPORT: playback toolbar, wide map, inspection rail; device list below.
   FORM: existing fleet workspace, no new identity or raster assets. */
export function FleetMonitor({ onViewTrip, client, session }: { onViewTrip: (driver: DemoDriver) => void; client: RoadSignalApiClient; session: SessionSnapshot | null }) {
  const [mode, setMode] = useState<"replay" | "connected">("replay");
  const isConnected = mode === "connected";
  const replay = useDemoReplay(!isConnected);
  const connected = useConnectedMonitoring(client, isConnected);
  const { vehicles, sensors } = isConnected ? connected : replay;
  const animating = isConnected ? !replay.reducedMotion && !connected.error : replay.animating;
  const [selectedVehicle, setSelectedVehicle] = useState<string | null>("CA 482-771");
  const [selectedSensor, setSelectedSensor] = useState<string | null>(null);
  const [selectedRoute, setSelectedRoute] = useState("route-balanced");
  const [fitKey, setFitKey] = useState(0);
  const [layer, setLayer] = useState<"vehicles" | "sensors">("vehicles");
  const chooseVehicle = useCallback((id: string) => {
    setSelectedVehicle(id); setSelectedSensor(null); setLayer("vehicles");
    const routeId = demoDrivers.find((driver) => driver.vehicle === id)?.activeTrip?.routeId;
    if (routeId) setSelectedRoute(routeId);
  }, []);
  const chooseSensor = useCallback((id: string) => { setSelectedSensor(id); setSelectedVehicle(null); setLayer("sensors"); }, []);
  const telemetry = useMemo(() => ({ vehicles, sensors, selectedVehicle, selectedSensor,
    onSelectVehicle: chooseVehicle, onSelectSensor: chooseSensor, animating, fitKey,
  }), [vehicles, sensors, selectedVehicle, selectedSensor, chooseVehicle, chooseSensor, animating, fitKey]);
  const vehicle = vehicles.find((item) => item.id === selectedVehicle);
  const sensor = sensors.find((item) => item.id === selectedSensor);
  const driver = demoDrivers.find((item) => item.vehicle === selectedVehicle);
  const elapsed = Math.floor(replay.seconds);
  const clock = `${String(Math.floor(elapsed / 60)).padStart(2, "0")}:${String(elapsed % 60).padStart(2, "0")}`;
  return (
    <div ref={replay.element} className="fleet-monitor" data-playing={animating} role="region" aria-label="Demo fleet monitoring">
      <header className="monitor-heading">
        <div><h2>{isConnected ? "Connected demo fleet" : "Fleet replay"}</h2><p>Follow a vehicle or inspect a street sensor.</p></div>
        <span className="demo-source-label">Simulated devices</span>
      </header>
      <div className="monitor-source-controls" role="group" aria-label="Monitoring data source">
        <button type="button" aria-pressed={!isConnected} onClick={() => setMode("replay")}>Local replay</button>
        <button type="button" aria-pressed={isConnected} disabled={deployment.demoOnly} aria-describedby={deployment.demoOnly ? "connected-demo-unavailable" : undefined} onClick={() => setMode("connected")}>Connected demo</button>
        <span>{isConnected ? "Server-supplied synthetic packets" : "Runs in this browser"}</span>
      </div>
      {deployment.demoOnly && <p className="monitor-note" id="connected-demo-unavailable">Connected monitoring needs the Docker services or a configured HTTPS backend. This GitHub Pages showcase runs the local replay only.</p>}
      {!isConnected && <div className="replay-controls" role="group" aria-label="Demo replay controls">
        <button type="button" className="replay-toggle" onClick={replay.toggle} aria-label={replay.playing ? "Pause demo replay" : "Play demo replay"}>
          <span className={`playback-symbol ${replay.playing ? "pause" : "play"}`} aria-hidden="true" />{replay.playing ? "Pause" : "Play"}
        </button>
        <button type="button" onClick={replay.reset}>Reset replay</button>
        <label>Speed<select aria-label="Demo playback speed" value={replay.speed} onChange={(event) => replay.setSpeed(Number(event.target.value))}>
          <option value={1}>1×</option><option value={4}>4×</option>
        </select></label>
        <div className="replay-timeline"><output aria-label="Demo elapsed time" data-seconds={elapsed}>{clock} <span>/ 03:00</span></output>
          <div className="replay-track" aria-hidden="true"><i style={{ transform: `scaleX(${replay.seconds / REPLAY_SECONDS})` }} /></div>
        </div>
        <span className="replay-status" role="status">{elapsed >= REPLAY_SECONDS ? "Replay complete" : replay.playing ? "Demo replay running" : "Demo replay paused"}</span>
      </div>}
      {isConnected && <div className="connected-status" role="status">
        <p>{connected.error ?? (connected.snapshot ? `Last accepted snapshot: ${timestampLabel(connected.snapshot.generated_at)}. Refreshes every 5 seconds.` : connected.loading ? "Connecting to the monitoring API…" : "No snapshot received.")}</p>
        <button type="button" onClick={connected.retry} disabled={connected.loading}>{connected.loading ? "Checking…" : "Refresh connection"}</button>
      </div>}
      {replay.reducedMotion && <p className="monitor-note">{isConnected ? "Reduced motion is on. Connected positions update without animation." : "Reduced motion is on. Replay starts paused and positions update without animation."}</p>}
      <div className="monitor-workspace">
        <div className="monitor-map-stage">
          <RouteMap routes={fallbackRoutes} selected={selectedRoute} onSelectRoute={setSelectedRoute} telemetry={telemetry} />
          <div className="monitor-map-footer"><span>{vehicles.length} demo trackers · {sensors.length} demo stations</span><button type="button" onClick={() => setFitKey((value) => value + 1)}>Fit network</button></div>
        </div>
        <section className="telemetry-inspector" aria-label="Selected device details">
          {vehicle && <div className="device-detail" key={vehicle.id}>
            <div className="device-heading"><span className={`device-token ${vehicle.state}`}>{vehicle.label}</span><div><h3>{vehicle.id}</h3><p>{vehicle.driver}</p></div></div>
            <p className={`device-state ${vehicle.state}`}><i aria-hidden="true" />{vehicle.state === "offline" ? "Offline · last known position" : vehicle.state === "idle" ? "Parked · ignition off" : vehicle.state === "arrived" ? "Arrived · replay complete" : "Moving · demo GPS"}</p>
            <dl className="device-readings">
              <div><dt>Sample speed</dt><dd>{vehicle.speedKmh === null ? "Unavailable" : <>{vehicle.speedKmh}<small> km/h</small></>}</dd></div>
              <div><dt>Last demo packet</dt><dd>{ageLabel(vehicle.ageSeconds)}</dd></div>
              <div><dt>GPS accuracy</dt><dd>{vehicle.accuracyMetres === null ? "Unavailable" : <>{vehicle.accuracyMetres}<small> m</small></>}</dd></div>
              <div><dt>Device battery</dt><dd>{vehicle.battery === null ? "Unavailable" : <>{vehicle.battery}<small>%</small></>}</dd></div>
            </dl>
            <div className="coordinate-readout"><span>Simulated coordinates</span><output aria-label="Selected demo vehicle coordinates">{vehicle.position.latitude.toFixed(5)}, {vehicle.position.longitude.toFixed(5)}</output></div>
            {vehicle.state === "offline" ? <p className="device-notice">No new packets. This marker stays at its last known position; current speed is unknown.</p>
              : <p className="device-notice">{isConnected ? "Synthetic packets received from the server demo. " : "Illustrative corridor replay. "}Sample speed and coordinates are not measurements from a real vehicle.</p>}
            {driver?.activeTrip && <button type="button" className="device-trip-button" onClick={() => onViewTrip(driver)}>Open driver’s demo trip</button>}
          </div>}
          {sensor && <div className="device-detail" key={sensor.id}>
            <div className="device-heading"><span className={`device-token sensor ${sensor.state}`}>{sensor.id}</span><div><h3>{sensor.name}</h3><p>Street-level sensor simulation</p></div></div>
            <p className={`device-state ${sensor.state}`}><i aria-hidden="true" />{sensor.state === "stale" ? "Stale · last sample retained" : "Reporting · simulated readings"}</p>
            <dl className="device-readings sensor-readings">
              <div><dt>Air temperature</dt><dd>{sensor.airC === null ? "Unavailable" : <>{sensor.airC.toFixed(1)}<small> °C</small></>}</dd></div>
              <div><dt>Road surface</dt><dd>{sensor.surfaceC === null ? "Unavailable" : <>{sensor.surfaceC.toFixed(1)}<small> °C</small></>}</dd></div>
              <div><dt>Rain rate</dt><dd>{sensor.rainMmH === null ? "Unavailable" : <>{sensor.rainMmH.toFixed(1)}<small> mm/h</small></>}</dd></div>
              <div><dt>Visibility</dt><dd>{sensor.visibilityM === null ? "Unavailable" : <>{(sensor.visibilityM / 1000).toFixed(1)}<small> km</small></>}</dd></div>
              <div><dt>Vehicle flow</dt><dd>{sensor.vehiclesPerMinute === null ? "Unavailable" : <>{sensor.vehiclesPerMinute}<small> /min</small></>}</dd></div>
              <div><dt>Mean traffic speed</dt><dd>{sensor.averageSpeedKmh === null ? "Unavailable" : <>{sensor.averageSpeedKmh}<small> km/h</small></>}</dd></div>
            </dl>
            <p className="sample-age">Last demo sample: {ageLabel(sensor.ageSeconds)}</p>
            <p className="device-notice">{sensor.state === "stale" ? "Readings are frozen, not current. " : ""}No physical sensor is connected. These values do not replace the weather feed or change route safety scores.</p>
          </div>}
          {!vehicle && !sensor && <p className="device-notice">{vehicles.length || sensors.length ? "Select a device to inspect its latest accepted packet." : "No connected devices received. Check the API connection and server demo producer; no local replay values are shown in this mode."}</p>}
        </section>
      </div>
      <div className="device-switcher" role="group" aria-label="Device list selection">
        <button type="button" aria-pressed={layer === "vehicles"} onClick={() => chooseVehicle(selectedVehicle ?? vehicles[0]?.id ?? "CA 482-771")}>Vehicle trackers <span>{vehicles.length}</span></button>
        <button type="button" aria-pressed={layer === "sensors"} onClick={() => chooseSensor(selectedSensor ?? sensors[0]?.id ?? "S1")}>Street sensors <span>{sensors.length}</span></button>
        <span>Select a device to inspect it</span>
      </div>
      {layer === "vehicles" ? <ul className="device-list" aria-label="Demo vehicle trackers">
        {vehicles.map((item) => <li key={item.id}><button type="button" aria-pressed={selectedVehicle === item.id} onClick={() => chooseVehicle(item.id)}>
          <span className={`device-token ${item.state}`}>{item.label}</span><span className="device-list-name"><strong>{item.id}</strong><small>{item.state === "offline" ? "Offline" : item.state === "idle" ? "Parked" : item.state === "arrived" ? "Arrived" : `${item.speedKmh} km/h · sample`}</small></span>
        </button></li>)}
      </ul> : <ul className="device-list stations" aria-label="Demo street sensors">
        {sensors.map((item) => <li key={item.id}><button type="button" aria-pressed={selectedSensor === item.id} onClick={() => chooseSensor(item.id)}>
          <span className={`device-token sensor ${item.state}`}>{item.id}</span><span className="device-list-name"><strong>{item.name}</strong><small>{item.state === "stale" ? `Stale · ${ageLabel(item.ageSeconds)}` : "Simulated station"}</small></span>
        </button></li>)}
      </ul>}
      <p className="monitor-note">{isConnected ? "All connected trackers and sensor readings above are synthetic server data. They do not change route safety scores or replace weather observations." : "All trackers and sensor readings above are synthetic. Playback is accelerated along illustrative Cape Town corridors and pauses offscreen. No news verification, camera analysis or physical device connection is implied."}</p>
      {isConnected && <MonitoringAutomation client={client} session={session} snapshot={connected.snapshot} connectionLost={!!connected.error} />}
    </div>
  );
}
