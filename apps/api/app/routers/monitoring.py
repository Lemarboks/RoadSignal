"""Synthetic telemetry and an evidence inbox; never changes public incident state."""
from datetime import date, datetime, timezone
from pathlib import Path
import secrets
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.security import HTTPAuthorizationCredentials

from ..auth import Principal, bearer, require_roles, require_when_enabled
from ..config import settings
from ..monitoring_repository import monitoring_repository
from ..monitoring_schemas import AutomationRun, EvidenceDecision, EvidenceSubmit, TelemetryIngest

router = APIRouter(prefix="/api/v1/monitoring", tags=["monitoring"])
operator = require_roles("administrator", "incident_moderator")
DAILY_PREFIX = "n8n-daily:"
DAILY_REPORT_RETENTION = 31


def utcnow():
    return datetime.now(timezone.utc)


def internal_token(credentials: HTTPAuthorizationCredentials | None = Depends(bearer)):
    """Only an explicitly mounted secret enables internal automation writes."""
    if not settings.monitoring_token_file:
        raise HTTPException(503, "Monitoring automation is not configured")
    try:
        with Path(settings.monitoring_token_file).open(encoding="utf-8") as secret:
            expected = secret.read(514).strip()
    except (OSError, UnicodeError):
        raise HTTPException(503, "Monitoring automation is not configured") from None
    if not 32 <= len(expected) <= 512 or not expected.isascii():
        raise HTTPException(503, "Monitoring automation is not configured")
    if not credentials or not secrets.compare_digest(credentials.credentials.encode(), expected.encode()):
        raise HTTPException(401, "Monitoring automation token is invalid", headers={"WWW-Authenticate": "Bearer"})


def age_seconds(device, now):
    return max(0, int((now - datetime.fromisoformat(device["reported_at"])).total_seconds()))


def stale(device, now):
    return device["state"] in {"offline", "stale"} or age_seconds(device, now) >= settings.monitoring_stale_seconds


@router.get("")
def snapshot(principal=Depends(require_when_enabled)):
    state = monitoring_repository.read()
    now = utcnow()
    return {
        "source": "demo", "generated_at": now.isoformat(),
        "devices": [dict(device, age_seconds=age_seconds(device, now), is_stale=stale(device, now))
                    for device in state.get("devices", {}).values()],
        "alerts": state.get("alerts", []), "summary": state.get("summary"),
        "automation": {
            "configured": bool(settings.monitoring_token_file),
            "last_run_at": state.get("last_run_at"), "last_run_key": state.get("last_run_key"),
            "run_count": state.get("run_count", 0),
        },
        "retention": {"devices": 500, "resolved_alerts": 500, "run_keys": 1000,
                      "review_entries": 1000, "daily_reports": DAILY_REPORT_RETENTION},
        "source_systems": {"vehicle_positions": "demo", "street_sensors": "demo",
                           "evidence": "operator_review", "automatic_incident_publication": False},
        "notice": "Synthetic devices only. These samples and automation alerts never change route safety scores.",
    }


@router.post("/internal/telemetry", dependencies=[Depends(internal_token)])
def ingest(body: TelemetryIngest):
    now = utcnow()

    def update(state):
        devices = state.setdefault("devices", {})
        if len(set(devices) | {device.id for device in body.devices}) > 500:
            raise HTTPException(409, "The demonstration workspace supports at most 500 devices")
        accepted, ignored = 0, 0
        for device in body.devices:
            existing = devices.get(device.id)
            if existing and existing["kind"] != device.kind:
                raise HTTPException(409, "A device id cannot change kind")
            if existing and device.reported_at <= datetime.fromisoformat(existing["reported_at"]):
                ignored += 1
                continue
            devices[device.id] = dict(device.model_dump(mode="json"), received_at=now.isoformat())
            accepted += 1
        return {"source": "demo", "accepted": accepted, "ignored": ignored, "received_at": now.isoformat()}

    return monitoring_repository.mutate(update)


@router.post("/internal/automation/run", dependencies=[Depends(internal_token)])
def run_automation(body: AutomationRun):
    now = utcnow()
    daily = body.run_key.startswith(DAILY_PREFIX)
    if daily:
        day = body.run_key[len(DAILY_PREFIX):]
        try:
            if date.fromisoformat(day).isoformat() != day:
                raise ValueError("noncanonical date")
        except ValueError:
            raise HTTPException(422, "Daily report keys require n8n-daily:YYYY-MM-DD with a valid calendar date") from None

    def remember_daily(state, result):
        reports = state.setdefault("daily_reports", [])
        reports.append(result)
        state["daily_reports"] = sorted(reports, key=lambda report: report["run_key"])[-DAILY_REPORT_RETENTION:]

    def update(state):
        runs = state.setdefault("runs", [])
        if daily:
            archived = next((report for report in state.get("daily_reports", [])
                             if report["run_key"] == body.run_key), None)
            if archived:
                return dict(archived, deduplicated=True)
        previous = next((run for run in runs if run["run_key"] == body.run_key), None)
        if previous:
            if daily:
                # Existing workspaces may contain a pre-archive daily run.
                remember_daily(state, previous)
            return dict(previous, deduplicated=True)
        devices = state.get("devices", {})
        alerts = state.setdefault("alerts", [])
        open_alerts = {alert["device_id"]: alert for alert in alerts if alert["status"] == "open"}
        stale_devices = {key for key, device in devices.items() if stale(device, now)}
        opened = resolved = 0
        for device_id in stale_devices:
            if device_id not in open_alerts:
                alerts.append({
                    "id": str(uuid4()), "kind": "stale_device", "device_id": device_id,
                    "source": "demo", "status": "open", "opened_at": now.isoformat(),
                    "resolved_at": None,
                    "message": f"Demo device {devices[device_id]['label']} has stale telemetry.",
                })
                opened += 1
        for device_id, alert in open_alerts.items():
            if device_id not in stale_devices:
                alert.update(status="resolved", resolved_at=now.isoformat())
                resolved += 1
        state["alerts"] = ([alert for alert in alerts if alert["status"] == "resolved"][-500:]
                           + [alert for alert in alerts if alert["status"] == "open"])
        summary = {
            "source": "demo", "generated_at": now.isoformat(), "devices_total": len(devices),
            "vehicles_total": sum(device["kind"] == "vehicle" for device in devices.values()),
            "sensors_total": sum(device["kind"] == "sensor" for device in devices.values()),
            "fresh_devices": len(devices) - len(stale_devices), "stale_devices": len(stale_devices),
            "open_alerts": len(stale_devices),
        }
        result = {"run_key": body.run_key, "started_at": now.isoformat(), "source": "demo",
                  "deduplicated": False, "new_alerts": opened, "resolved_alerts": resolved, "summary": summary}
        runs.append(result)
        state["runs"] = runs[-1000:]
        if daily:
            remember_daily(state, result)
        state.update(summary=summary, last_run_at=now.isoformat(), last_run_key=body.run_key,
                     run_count=state.get("run_count", 0) + 1)
        return result

    return monitoring_repository.mutate(update)


@router.get("/reports")
def daily_reports(principal: Principal = Depends(operator)):
    reports = monitoring_repository.read().get("daily_reports", [])
    return {
        "items": sorted(reports, key=lambda report: report["run_key"], reverse=True),
        "retention_entries": DAILY_REPORT_RETENTION,
        "notice": "The latest 31 scheduled demo snapshots, not verified live fleet reports.",
    }


@router.post("/internal/evidence", dependencies=[Depends(internal_token)])
def submit_evidence(body: EvidenceSubmit):
    now = utcnow()
    incoming = body.model_dump(mode="json")

    def update(state):
        reviews = state.setdefault("reviews", [])
        existing = next((review for review in reviews if review["source"] == body.source
                         and review["event_id"] == body.event_id), None)
        if existing:
            if any(existing[key] != value for key, value in incoming.items()):
                raise HTTPException(409, "This evidence id already has a different submission")
            return dict(existing, deduplicated=True)
        # Never silently discard pending reviews or operator decisions.
        if len(reviews) >= 1000:
            raise HTTPException(409, "The review inbox is full; archive it before adding evidence")
        review = dict(incoming, id=str(uuid4()), status="pending", created_at=now.isoformat(),
                      reviewed_at=None, reviewed_by=None, review_note=None,
                      decision_scope="evidence_review_only", incident_published=False)
        reviews.append(review)
        return dict(review, deduplicated=False)

    return monitoring_repository.mutate(update)


@router.get("/evidence")
def evidence_inbox(
    status: str | None = Query(default=None, pattern="^(pending|approved|rejected)$"),
    limit: int = Query(default=100, ge=1, le=500),
    principal: Principal = Depends(operator),
):
    reviews = monitoring_repository.read().get("reviews", [])
    selected = [review for review in reversed(reviews) if status is None or review["status"] == status]
    return {"items": selected[:limit], "total": len(selected),
            "notice": "Approval records an operator evidence decision. It does not verify or publish a road incident."}


@router.post("/evidence/{review_id}/decision")
def decide_evidence(review_id: str, body: EvidenceDecision, principal: Principal = Depends(operator)):
    now = utcnow()

    def update(state):
        review = next((item for item in state.get("reviews", []) if item["id"] == review_id), None)
        if review is None:
            raise HTTPException(404, "Evidence review not found")
        if review["status"] != "pending":
            raise HTTPException(409, "This evidence review already has an operator decision")
        review.update(status=body.decision, reviewed_at=now.isoformat(), reviewed_by=str(principal.id),
                      review_note=body.note)
        return review

    return monitoring_repository.mutate(update)
