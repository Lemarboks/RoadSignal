from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from fastapi.testclient import TestClient
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.auth import Principal, current_principal
from app.config import settings
from app.database.models import MonitoringState
from app.main import app
from app.monitoring_repository import MemoryMonitoringRepository, MySQLMonitoringRepository
from app.monitoring_schemas import AutomationRun
from app.routers import monitoring
from app.store import INCIDENTS, TRIPS

PREFIX = "/api/v1/monitoring"
TOKEN = "test-only-monitoring-token-" + "a" * 32


@pytest.fixture
def workspace(monkeypatch, tmp_path):
    repository = MemoryMonitoringRepository()
    monkeypatch.setattr(monitoring, "monitoring_repository", repository)
    token_file = tmp_path / "monitoring-token"
    token_file.write_text(TOKEN, encoding="utf-8")
    monkeypatch.setattr(settings, "monitoring_token_file", str(token_file))
    monkeypatch.setattr(settings, "monitoring_stale_seconds", 120)
    monkeypatch.setattr(settings, "require_auth", False)
    app.dependency_overrides.pop(current_principal, None)
    yield TestClient(app), repository, token_file
    app.dependency_overrides.pop(current_principal, None)


def headers(token=TOKEN):
    return {"Authorization": f"Bearer {token}"}


def device(identifier="V1", **changes):
    return {
        "id": identifier, "kind": "vehicle", "label": "Demo vehicle", "source": "demo",
        "state": "moving", "reported_at": datetime.now(timezone.utc).isoformat(),
        "latitude": -33.93, "longitude": 18.44, "readings": {"speedKmh": 40, "battery": 90},
        **changes,
    }


def ingest(client, *devices):
    return client.post(PREFIX + "/internal/telemetry", headers=headers(), json={"source": "demo", "devices": list(devices)})


def run(client, key="scheduled-1"):
    return client.post(PREFIX + "/internal/automation/run", headers=headers(), json={"run_key": key})


def evidence(**changes):
    return {"event_id": "claim-1", "source": "submitted", "claim": "A closure was reported near the station.",
            "evidence": [{"text": "The supplied report describes a temporary road closure.",
                          "source_url": "https://example.com/report"}],
            "analysis": {"model": "demo-nli", "results": [{"label": "supports", "score": 0.8}]}, **changes}


def submit(client, body=None):
    return client.post(PREFIX + "/internal/evidence", headers=headers(), json=body or evidence())


def become(role):
    principal = Principal(uuid4(), "operator@example.com", "Test operator", role)
    app.dependency_overrides[current_principal] = lambda: principal
    return principal


def test_empty_snapshot_is_explicitly_demo_and_does_not_invent_an_automation_run(workspace):
    client, _, _ = workspace
    data = client.get(PREFIX).json()
    assert data["source"] == "demo" and data["devices"] == [] and data["summary"] is None
    assert data["automation"]["run_count"] == 0
    assert data["source_systems"]["automatic_incident_publication"] is False


@pytest.mark.parametrize("path,body", [
    ("/internal/telemetry", {"source": "demo", "devices": [device()]}),
    ("/internal/automation/run", {"run_key": "one"}),
    ("/internal/evidence", evidence()),
])
def test_internal_endpoints_require_the_separate_token(workspace, path, body):
    client, _, _ = workspace
    assert client.post(PREFIX + path, json=body).status_code == 401
    assert client.post(PREFIX + path, headers=headers("incorrect"), json=body).status_code == 401


@pytest.mark.parametrize("content", ["", "short", "x" * 513, "non-ascii-" + "é" * 40])
def test_invalid_secret_files_fail_closed(workspace, content):
    client, _, token_file = workspace
    token_file.write_text(content, encoding="utf-8")
    response = run(client)
    assert response.status_code == 503
    assert str(token_file) not in response.text


def test_unconfigured_or_missing_secret_files_fail_closed(workspace, monkeypatch):
    client, _, token_file = workspace
    monkeypatch.setattr(settings, "monitoring_token_file", "")
    assert run(client).status_code == 503
    monkeypatch.setattr(settings, "monitoring_token_file", str(token_file.parent / "not-present"))
    assert run(client).status_code == 503


def test_secret_rotation_is_effective_without_restart(workspace):
    client, _, token_file = workspace
    assert run(client).status_code == 200
    replacement = "replacement-token-" + "b" * 40
    token_file.write_text(replacement, encoding="utf-8")
    assert run(client, "two").status_code == 401
    response = client.post(PREFIX + "/internal/automation/run", headers=headers(replacement), json={"run_key": "two"})
    assert response.status_code == 200


@pytest.mark.parametrize("changes", [
    {"source": "real"}, {"latitude": 91}, {"longitude": -181},
    {"reported_at": "2026-01-01T00:00:00"},
    {"reported_at": (datetime.now(timezone.utc) + timedelta(days=1)).isoformat()},
    {"readings": {"driver": "A person"}}, {"readings": {"speedKmh": "NaN"}},
    {"readings": {"x" * 49: 1}}, {"state": "reporting"}, {"extra": "rejected"},
])
def test_telemetry_rejects_real_invalid_or_unbounded_inputs(workspace, changes):
    client, repository, _ = workspace
    assert ingest(client, device(**changes)).status_code == 422
    assert repository.read() == {}


def test_batch_rejects_duplicate_device_ids(workspace):
    client, _, _ = workspace
    assert ingest(client, device(), device()).status_code == 422


def test_ingest_preserves_numeric_samples_and_ignores_old_packets(workspace):
    client, _, _ = workspace
    fresh = device()
    assert ingest(client, fresh).json()["accepted"] == 1
    old = device(reported_at=(datetime.now(timezone.utc) - timedelta(minutes=10)).isoformat(), readings={"speedKmh": 99})
    assert ingest(client, old).json()["ignored"] == 1
    sample = client.get(PREFIX).json()["devices"][0]
    assert sample["readings"]["speedKmh"] == 40
    assert sample["source"] == "demo" and sample["is_stale"] is False
    assert sample["received_at"] and sample["age_seconds"] >= 0


def test_rejected_batch_rolls_back_earlier_changes(workspace):
    client, repository, _ = workspace
    assert ingest(client, device()).status_code == 200
    original = repository.read()
    response = ingest(client, device("V2"), device(kind="sensor", state="reporting"))
    assert response.status_code == 409
    assert repository.read() == original


def test_automation_dedupes_stale_alerts_and_recovers_only_after_fresh_packets(workspace, monkeypatch):
    client, _, _ = workspace
    now = datetime.now(timezone.utc)
    monkeypatch.setattr(monitoring, "utcnow", lambda: now)
    offline = device(state="offline", reported_at=(now - timedelta(minutes=10)).isoformat(), readings={"speedKmh": None})
    sensor = device("S1", kind="sensor", state="reporting", readings={"airC": 18.4}, reported_at=now.isoformat())
    assert ingest(client, offline, sensor).status_code == 200
    first = run(client).json()
    assert first["new_alerts"] == 1 and first["summary"]["stale_devices"] == 1
    assert first["summary"]["vehicles_total"] == first["summary"]["sensors_total"] == 1
    assert run(client).json()["deduplicated"] is True
    assert run(client, "two").json()["new_alerts"] == 0
    assert len(client.get(PREFIX).json()["alerts"]) == 1
    assert ingest(client, device(reported_at=now.isoformat())).status_code == 200
    recovered = run(client, "three").json()
    assert recovered["resolved_alerts"] == 1 and recovered["summary"]["open_alerts"] == 0
    assert client.get(PREFIX).json()["alerts"][0]["status"] == "resolved"
    monkeypatch.setattr(monitoring, "utcnow", lambda: now + timedelta(minutes=3))
    assert all(sample["is_stale"] for sample in client.get(PREFIX).json()["devices"])
    late = run(client, "four").json()
    assert late["new_alerts"] == 2 and late["summary"]["stale_devices"] == 2


def test_retrying_an_old_run_does_not_overwrite_the_current_summary(workspace):
    client, _, _ = workspace
    assert run(client, "first").json()["summary"]["devices_total"] == 0
    ingest(client, device())
    assert run(client, "second").json()["summary"]["devices_total"] == 1
    assert run(client, "first").json()["deduplicated"] is True
    data = client.get(PREFIX).json()
    assert data["summary"]["devices_total"] == 1 and data["automation"]["run_count"] == 2


def test_concurrent_automation_retry_is_atomic(workspace):
    _, repository, _ = workspace
    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(lambda _: monitoring.run_automation(AutomationRun(run_key="concurrent")), range(16)))
    assert sum(not item["deduplicated"] for item in results) == 1
    assert repository.read()["run_count"] == 1


@pytest.mark.parametrize("day", ["", "20260201", "2026-2-01", "2026-02-30", "2026-13-01", "2026-W01-1", "2026-09-12T07:00:00"])
def test_daily_report_keys_require_canonical_calendar_dates(workspace, day):
    client, repository, _ = workspace
    assert run(client, "n8n-daily:" + day).status_code == 422
    assert repository.read() == {}


def test_daily_report_archive_is_independent_of_current_summary_and_minute_run_retention(workspace):
    client, repository, _ = workspace
    daily_key = "n8n-daily:2026-09-12"
    initial = run(client, daily_key).json()
    assert initial["summary"]["devices_total"] == 0
    assert ingest(client, device()).status_code == 200
    # Exercise actual generic run eviction without 1,000 HTTP round trips.
    for index in range(1001):
        monitoring.run_automation(AutomationRun(run_key=f"n8n-health:{index}"))
    state = repository.read()
    assert len(state["runs"]) == 1000
    assert not any(item["run_key"] == daily_key for item in state["runs"])
    assert state["summary"]["devices_total"] == 1
    repeated = run(client, daily_key).json()
    assert repeated == dict(initial, deduplicated=True)
    assert repository.read() == state
    become("administrator")
    result = client.get(PREFIX + "/reports").json()
    assert result["retention_entries"] == 31
    assert result["items"] == [initial]
    assert result["items"][0]["source"] == "demo"


def test_daily_report_archive_retains_latest_31_dates_newest_first(workspace):
    client, repository, _ = workspace
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    keys = ["n8n-daily:" + (start + timedelta(days=index)).date().isoformat() for index in range(33)]
    for key in reversed(keys):
        assert run(client, key).status_code == 200
    assert len(repository.read()["daily_reports"]) == 31
    become("incident_moderator")
    result = client.get(PREFIX + "/reports").json()
    assert [item["run_key"] for item in result["items"]] == list(reversed(keys[-31:]))
    assert all(item["source"] == "demo" for item in result["items"])


def test_daily_report_archive_backfills_existing_run_without_changing_its_snapshot(workspace):
    client, repository, _ = workspace
    key = "n8n-daily:2026-02-28"
    initial = run(client, key).json()
    repository.mutate(lambda state: state.pop("daily_reports"))
    ingest(client, device())
    run(client, "newer-minute")
    assert run(client, key).json() == dict(initial, deduplicated=True)
    state = repository.read()
    assert state["daily_reports"] == [initial]
    assert state["summary"]["devices_total"] == 1
    assert state["run_count"] == 2


def test_daily_reports_always_require_operator_jwt(workspace):
    client, _, _ = workspace
    assert client.get(PREFIX + "/reports").status_code == 401
    assert client.get(PREFIX + "/reports", headers=headers()).status_code == 401
    for role in ("driver", "fleet_manager"):
        become(role)
        assert client.get(PREFIX + "/reports").status_code == 403
    for role in ("administrator", "incident_moderator"):
        become(role)
        response = client.get(PREFIX + "/reports")
        assert response.status_code == 200
        assert response.json()["items"] == []


@pytest.mark.parametrize("body", [
    evidence(source="real"), evidence(evidence=[{"text": "Unattributed source text"}]),
    evidence(evidence=[{"text": "Source text has a dangerous URL", "source_url": "javascript:alert(1)"}]),
    evidence(evidence=[{"text": "Source text contains a credential", "source_url": "https://person:password@example.com/report"}]),
    evidence(analysis={"results": list(range(101))}), evidence(analysis={"data": "x" * 65000}),
    evidence(incident_published=True), evidence(evidence=[]),
])
def test_evidence_rejects_missing_provenance_and_unbounded_analysis(workspace, body):
    client, _, _ = workspace
    assert submit(client, body).status_code == 422


def test_evidence_submission_is_idempotent_but_cannot_replace_a_claim(workspace):
    client, _, _ = workspace
    first = submit(client).json()
    second = submit(client).json()
    assert first["id"] == second["id"] and second["deduplicated"] is True
    assert first["status"] == "pending" and first["incident_published"] is False
    assert submit(client, evidence(claim="A different claim under the same event id.")).status_code == 409
    assert "claim" not in client.get(PREFIX).text


def test_operator_jwt_is_always_required_for_inbox_and_decisions(workspace):
    client, _, _ = workspace
    item = submit(client).json()
    decision = {"decision": "approved", "note": "Checked the supplied evidence."}
    assert client.get(PREFIX + "/evidence").status_code == 401
    assert client.get(PREFIX + "/evidence", headers=headers()).status_code == 401
    assert client.post(PREFIX + f"/evidence/{item['id']}/decision", json=decision).status_code == 401
    become("driver")
    assert client.get(PREFIX + "/evidence").status_code == 403
    assert client.post(PREFIX + f"/evidence/{item['id']}/decision", json=decision).status_code == 403
    become("fleet_manager")
    assert client.get(PREFIX + "/evidence").status_code == 403


@pytest.mark.parametrize("role,decision", [("administrator", "approved"), ("incident_moderator", "rejected")])
def test_operator_decisions_persist_actor_and_never_publish_incidents(workspace, role, decision):
    client, _, _ = workspace
    incidents_before, trips_before = deepcopy(INCIDENTS), deepcopy(TRIPS)
    ingest(client, device(state="offline"))
    run(client)
    item = submit(client).json()
    principal = become(role)
    assert client.get(PREFIX + "/evidence?status=pending").json()["total"] == 1
    response = client.post(PREFIX + f"/evidence/{item['id']}/decision", json={"decision": decision, "note": "Operator checked supplied evidence."})
    assert response.status_code == 200
    reviewed = response.json()
    assert reviewed["status"] == decision and reviewed["reviewed_by"] == str(principal.id)
    assert reviewed["reviewed_at"] and reviewed["incident_published"] is False
    assert client.get(PREFIX + "/evidence?status=pending").json()["total"] == 0
    assert client.get(PREFIX + f"/evidence?status={decision}").json()["total"] == 1
    assert client.post(PREFIX + f"/evidence/{item['id']}/decision", json={"decision": "rejected", "note": "Overwrite decision"}).status_code == 409
    assert INCIDENTS == incidents_before and TRIPS == trips_before


def test_review_validates_decision_and_note_and_returns_missing_id(workspace):
    client, _, _ = workspace
    become("administrator")
    item = submit(client).json()
    path = PREFIX + f"/evidence/{item['id']}/decision"
    assert client.post(path, json={"decision": "verified", "note": "Not permitted"}).status_code == 422
    assert client.post(path, json={"decision": "approved", "note": "   "}).status_code == 422
    assert client.post(PREFIX + "/evidence/missing/decision", json={"decision": "rejected", "note": "Missing item"}).status_code == 404


def test_memory_read_is_a_copy_and_failed_mutations_roll_back():
    repository = MemoryMonitoringRepository()
    repository.mutate(lambda state: state.update(value={"nested": 1}))
    repository.read()["value"]["nested"] = 2
    def fail(state):
        state["value"]["nested"] = 3
        raise ValueError("rollback")
    with pytest.raises(ValueError):
        repository.mutate(fail)
    assert repository.read()["value"]["nested"] == 1


def test_sql_repository_persists_between_instances_and_rolls_back(tmp_path):
    # SQLite checks JSON persistence/transactions; the MySQL integration check
    # additionally exercises the deployed dialect and migration-created row.
    engine = create_engine("sqlite:///" + str(tmp_path / "monitoring.db"))
    MonitoringState.__table__.create(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    with factory.begin() as db:
        db.add(MonitoringState(id="demo", payload={}))
    first, second = MySQLMonitoringRepository(factory), MySQLMonitoringRepository(factory)
    first.mutate(lambda state: state.update(value={"nested": 1}))
    assert second.read() == {"value": {"nested": 1}}
    def fail(state):
        state["value"]["nested"] = 2
        raise ValueError("rollback")
    with pytest.raises(ValueError):
        first.mutate(fail)
    assert second.read()["value"]["nested"] == 1
    engine.dispose()
