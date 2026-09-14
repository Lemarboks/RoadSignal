"""Fast simulator/provisioning contract checks; no services or network needed."""
import importlib.util
import json
from pathlib import Path
import sys
from urllib.parse import parse_qs, urlparse

import pytest

ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT))
import bridge


def test_corridor_turnarounds_do_not_teleport():
    for index in range(2):
        for boundary in (600, 1200):
            before = bridge.path_position(index, boundary - .01)
            after = bridge.path_position(index, boundary + .01)
            assert abs(before[0] - after[0]) < .00001
            assert abs(before[1] - after[1]) < .00001
        assert 0 <= bridge.path_position(index, 400)[3] <= 100


def test_gps_is_read_back_from_traccar_and_speed_round_trips(monkeypatch, tmp_path):
    (tmp_path / "accounts.json").write_text(json.dumps({"traccar": {"email": "test", "password": "test"}}))
    (tmp_path / "traccar-devices.json").write_text(json.dumps({plate: {"id": i, "uniqueId": str(i)} for i, plate in enumerate(bridge.PLATES)}))
    monkeypatch.setattr(bridge, "ROOT", tmp_path)
    packets = []
    class Response:
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def read(self, size): return b""
    def send(url, timeout):
        packets.append(parse_qs(urlparse(url).query))
        return Response()
    monkeypatch.setattr(bridge, "urlopen", send)
    queries = []
    def get(url, headers):
        queries.append(url)
        if len(queries) == 1:
            return []
        return [{"deviceId": int(p["id"][0]), "latitude": float(p["lat"][0]), "longitude": float(p["lon"][0]),
                 "speed": float(p["speed"][0]), "course": 25, "fixTime": "2026-01-01T00:00:00Z",
                 "accuracy": 5, "attributes": {"batteryLevel": 90}} for p in packets]
    monkeypatch.setattr(bridge, "request", get)
    output = bridge.traccar_cycle(0)
    assert len(output) == 4 and len(queries) == 2
    assert output[0]["readings"]["speedKmh"] == 35
    assert output[3]["state"] == "offline" and "speedKmh" not in output[3]["readings"]
    assert all(item["source"] == "demo" for item in output)


def test_upstream_failure_does_not_produce_fabricated_packets(monkeypatch, tmp_path):
    monkeypatch.setattr(bridge, "ROOT", tmp_path)
    import pytest
    with pytest.raises(FileNotFoundError):
        bridge.traccar_cycle(0)
    with pytest.raises(FileNotFoundError):
        bridge.SensorBridge().cycle(0)


@pytest.mark.parametrize("value", [None, True, {}, [], "unavailable", "nan", "inf", float("nan")])
def test_sensor_null_and_invalid_readings_are_not_observations(value):
    assert bridge.sensor_sample({"airC": [{"ts": 1000, "value": value}]}, ["airC"]) is None


def test_sensor_sample_uses_oldest_upstream_timestamp():
    assert bridge.sensor_sample({"airC": [{"ts": 3000, "value": "17.8"}],
                                 "surfaceC": [{"ts": 2000, "value": 21.4}]},
                                ["airC", "surfaceC"]) == (2, {"airC": 17.8, "surfaceC": 21.4})


@pytest.mark.parametrize("delayed", [False, True])
def test_sensors_seed_null_placeholders_and_read_back_actual_upstream_samples(monkeypatch, tmp_path, delayed):
    (tmp_path / "accounts.json").write_text(json.dumps({"thingsboard": {"tenant": "test"}}))
    (tmp_path / "thingsboard-devices.json").write_text(json.dumps(
        {sid: {"id": sid, "token": "test-" + sid} for sid, *_ in bridge.SENSORS}))
    monkeypatch.setattr(bridge, "ROOT", tmp_path)
    monkeypatch.setattr(bridge, "tb_login", lambda *args: {"X-Authorization": "test"})
    monkeypatch.setattr(bridge.time, "time", lambda: 2_000_000)
    stored, posts = {}, []

    def upstream(url, body=None, headers=None):
        if body is not None:
            sid = url.split("test-")[1].split("/")[0]
            posts.append((sid, body))
            if sid != "S3" or not delayed:
                # The relay must use the response, not the simulated values.
                stored[sid] = {key: [{"ts": body["ts"] - 250, "value": str(value + .1)}]
                               for key, value in body["values"].items()}
            return None
        sid = url.split("/DEVICE/")[1].split("/")[0]
        keys = parse_qs(urlparse(url).query)["keys"][0].split(",")
        return stored.get(sid, {key: [{"ts": 0, "value": None}] for key in keys})

    monkeypatch.setattr(bridge, "request", upstream)
    sensors = bridge.SensorBridge()
    output = sensors.cycle(0)
    assert [sid for sid, _ in posts] == ["S1", "S2", "S3"]
    assert len(output) == (2 if delayed else 3)
    assert output[0]["readings"]["airC"] == pytest.approx(17.9)
    assert output[0]["reported_at"] == bridge.iso(2_000_000 - .25)
    assert all(item["source"] == "demo" for item in output)
    if not delayed:
        assert output[2]["reported_at"] == bridge.iso(2_000_000 - 720 - .25)
        assert output[2]["state"] == "stale"
        posts.clear()
        repeated = sensors.cycle(5)
        assert [sid for sid, _ in posts] == ["S1", "S2"]
        assert repeated[2] == output[2] # Existing stale readings are never refreshed.


def test_workflows_have_only_fixed_internal_targets_and_no_embedded_secrets():
    workflows = [json.loads(path.read_text(encoding="utf-8")) for path in (ROOT / "workflows").glob("*.json")]
    assert len(workflows) == 3
    for workflow in workflows:
        assert workflow["active"] is False # Installation explicitly publishes the reviewed versions.
        for node in workflow["nodes"]:
            if node["type"].endswith("httpRequest"):
                assert urlparse(node["parameters"]["url"]).hostname in {"api", "verification"}
            if node["type"].endswith("webhook"):
                assert node["parameters"]["authentication"] == "headerAuth"
    evidence = next(w for w in workflows if w["id"] == "roadsignal-evidence")
    assert "Queue for operator review" in {node["name"] for node in evidence["nodes"]}
    assert all("incidents" not in node["parameters"].get("url", "") for node in evidence["nodes"])
