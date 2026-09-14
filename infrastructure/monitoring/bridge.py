"""Synthetic devices -> actual local Traccar/ThingsBoard -> RoadSignal snapshot.

Nothing goes straight from the simulator into RoadSignal. A stopped upstream
retains its old timestamp in the API, so outages remain visible to n8n/UI.
"""
from datetime import datetime, timezone
import json
import math
import os
import time
from urllib.parse import urlencode
from urllib.request import urlopen

from bootstrap import ROOT, basic, request, tb_login

API = os.environ.get("API_URL", "http://api:8000")
TRACCAR = os.environ.get("TRACCAR_URL", "http://traccar:8082")
THINGSBOARD = os.environ.get("THINGSBOARD_URL", "http://thingsboard:8080")
PLATES = ["CA 482-771", "CA 193-044", "CY 827-519", "CA 614-208"]
PATHS = [
    [(-33.925, 18.424), (-33.928, 18.438), (-33.931, 18.45), (-33.933, 18.464), (-33.942, 18.478), (-33.947, 18.493)],
    [(-33.94, 18.479), (-33.947, 18.501), (-33.955, 18.522), (-33.962, 18.543), (-33.963, 18.564), (-33.965, 18.591)],
]
SENSORS = [
    ("S1", "Woodstock station", -33.9337, 18.4477, 17.8, 21.4, 0.2, 8100, 24, 46),
    ("S2", "Athlone station", -33.9585, 18.521, 16.2, 18.1, 1.6, 3600, 43, 29),
    ("S3", "Airport approach station", -33.967, 18.59, 18.1, 23.7, 0, 9500, 18, 61),
]


def iso(seconds):
    return datetime.fromtimestamp(seconds, timezone.utc).isoformat()


def path_position(index, seconds):
    # A slow out-and-back demo corridor; no jump between loop ends.
    phase = seconds % 1200 / 600
    progress = phase if phase <= 1 else 2 - phase
    points = PATHS[index]
    offset = progress * (len(points) - 1)
    segment = min(len(points) - 2, int(offset))
    fraction = offset - segment
    a, b = points[segment], points[segment + 1]
    lat, lon = a[0] + (b[0] - a[0]) * fraction, a[1] + (b[1] - a[1]) * fraction
    heading = (math.degrees(math.atan2((b[1] - a[1]) * math.cos(math.radians(lat)), b[0] - a[0])) + (180 if phase > 1 else 0)) % 360
    return lat, lon, heading, progress * 100


def traccar_cycle(seconds):
    accounts = json.loads((ROOT / "accounts.json").read_text())["traccar"]
    devices = json.loads((ROOT / "traccar-devices.json").read_text())
    headers = basic(accounts["email"], accounts["password"])
    previous = {p["deviceId"]: p for p in request(TRACCAR + "/api/positions", headers=headers)}
    progress_by_id = {}
    for index, plate in enumerate(PLATES):
        if index == 3 and devices[plate]["id"] in previous:
            continue
        if index < 2:
            lat, lon, heading, progress = path_position(index, seconds + index * 140)
            speed = 35 + index * 12 + round(3 * math.sin(seconds / 30))
        else:
            lat, lon = (-33.925, 18.433) if index == 2 else (-33.9406, 18.5047)
            heading, progress, speed = 0, 0, 0
        stamp = time.time() - (28 * 60 if index == 3 else 0)
        query = urlencode({"id": devices[plate]["uniqueId"], "lat": lat, "lon": lon,
                           "timestamp": int(stamp), "speed": round(speed / 1.852, 4), "bearing": heading, "accuracy": 5,
                           "batt": 90 - index * 18})
        # OsmAnd is a separate internal HTTP listener. No host exposure is needed.
        with urlopen("http://traccar:5055/?" + query, timeout=10) as response:
            response.read(4096)
        progress_by_id[plate] = progress
    positions = {p["deviceId"]: p for p in request(TRACCAR + "/api/positions", headers=headers)}
    output = []
    for index, plate in enumerate(PLATES):
        p = positions.get(devices[plate]["id"])
        if not p:
            continue
        # Traccar stores knots, regardless of the incoming protocol's units.
        readings = {"heading": p["course"], "battery": p.get("attributes", {}).get("batteryLevel", 0),
                    "progress": progress_by_id.get(plate, 0), "accuracyMetres": p.get("accuracy", 0)}
        if index != 3:
            readings["speedKmh"] = round(p["speed"] * 1.852, 1)
        output.append({"id": plate, "kind": "vehicle", "label": f"V{index + 1}", "source": "demo",
                       "state": "offline" if index == 3 else "idle" if index == 2 else "moving",
                       "reported_at": p["fixTime"], "latitude": p["latitude"], "longitude": p["longitude"],
                       "readings": readings})
    return output


def sensor_sample(latest, keys):
    """Decode complete upstream readings; null placeholders are not observations."""
    if not isinstance(latest, dict):
        return None
    readings, timestamps = {}, []
    for key in keys:
        rows = latest.get(key)
        if not isinstance(rows, list) or not rows or not isinstance(rows[0], dict):
            return None
        value, stamp = rows[0].get("value"), rows[0].get("ts")
        if (isinstance(value, bool) or not isinstance(value, (str, int, float))
                or isinstance(stamp, bool) or not isinstance(stamp, (int, float))):
            return None
        try:
            number = float(value)
        except ValueError:
            return None
        if not math.isfinite(number) or not math.isfinite(stamp) or stamp <= 0:
            return None
        readings[key] = number
        timestamps.append(stamp)
    return min(timestamps) / 1000, readings


class SensorBridge:
    def __init__(self):
        self.headers = None
        self.expires = 0

    def cycle(self, seconds):
        devices = json.loads((ROOT / "thingsboard-devices.json").read_text())
        if time.time() >= self.expires:
            password = json.loads((ROOT / "accounts.json").read_text())["thingsboard"]["tenant"]
            self.headers = tb_login(THINGSBOARD, "tenant", password)
            self.expires = time.time() + 1200
        keys = ["airC", "surfaceC", "rainMmH", "visibilityM", "vehiclesPerMinute", "averageSpeedKmh"]
        output = []
        for sid, label, lat, lon, *values in SENSORS:
            device = devices[sid]
            endpoint = THINGSBOARD + f"/api/plugins/telemetry/DEVICE/{device['id']}/values/timeseries?keys=" + ",".join(keys)
            old = request(endpoint, headers=self.headers)
            # ThingsBoard represents an unpopulated requested key with a truthy
            # [{"ts": ..., "value": null}] row. That must not suppress S3's
            # one-time stale seed or invalidate already collected S1/S2 samples.
            if sid != "S3" or sensor_sample(old, keys) is None:
                wave = round(math.sin(seconds / 30) * 0.4, 1) if sid != "S3" else 0
                values[0] = round(values[0] + wave, 1)
                stamp = int((time.time() - (12 * 60 if sid == "S3" else 0)) * 1000)
                request(THINGSBOARD + f"/api/v1/{device['token']}/telemetry", {"ts": stamp, "values": dict(zip(keys, values))})
            latest = request(endpoint, headers=self.headers)
            sample = sensor_sample(latest, keys)
            if sample is None:
                continue # Async persistence may not have caught up yet.
            stamp, readings = sample
            output.append({"id": sid, "kind": "sensor", "label": label, "source": "demo",
                           "state": "stale" if sid == "S3" else "reporting", "reported_at": iso(stamp),
                           "latitude": lat, "longitude": lon,
                           "readings": readings})
        return output


def main():
    token = (ROOT / "monitoring-token").read_text().strip()
    headers = {"Authorization": "Bearer " + token}
    sensors = SensorBridge()
    started = time.monotonic()
    status = {}
    while True:
        output = []
        for name, run in [("traccar", lambda: traccar_cycle(time.monotonic() - started)),
                          ("thingsboard", lambda: sensors.cycle(time.monotonic() - started))]:
            try:
                output.extend(run())
                state = "receiving demo packets"
            except Exception as error:
                # HTTP errors may contain credentials in URLs: don't log them.
                frame = error.__traceback__
                while frame.tb_next:
                    frame = frame.tb_next
                location = f"{frame.tb_frame.f_code.co_name}:{frame.tb_lineno}"
                state = f"unavailable ({type(error).__name__} at {location}); previous readings retained"
            if status.get(name) != state:
                print(name + ": " + state, flush=True)
                status[name] = state
        if output:
            try:
                request(API + "/api/v1/monitoring/internal/telemetry", {"source": "demo", "devices": output}, headers)
                if status.get("api") != "connected":
                    print("RoadSignal: storing upstream demo readings", flush=True)
                status["api"] = "connected"
            except Exception as error:
                state = type(error).__name__
                if status.get("api") != state:
                    print("RoadSignal ingest unavailable (" + state + ")", flush=True)
                status["api"] = state
        time.sleep(5)


if __name__ == "__main__":
    main()
