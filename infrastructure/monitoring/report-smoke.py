"""Verify the deployed daily archive and restart persistence without exposing secrets.

Run ``capture`` before restarting api, n8n and monitoring-bridge, then ``verify``.
Only the authenticated health webhook is triggered: this script never creates a
daily report directly or submits/decides evidence. Existing daily reports and an
operator decision are required, so missing production-path evidence fails closed.
The baseline is stored privately beside integration state; it contains no tokens,
passwords, evidence text, notes, images or coordinates.
"""
import argparse
import hashlib
import json
import os
from urllib.error import HTTPError

from bootstrap import ROOT, request, save

API = os.environ.get("API_URL", "http://api:8000")
N8N = os.environ.get("N8N_URL", "http://n8n:5678")
BASELINE = ROOT / "report-smoke-baseline.json"
STALE_IDS = {"CA 614-208", "S3"}


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()


def read_state(headers):
    snapshot = request(API + "/api/v1/monitoring", headers=headers)
    archive = request(API + "/api/v1/monitoring/reports", headers=headers)
    evidence = request(API + "/api/v1/monitoring/evidence?limit=500", headers=headers)
    reports = {report["run_key"]: digest(report) for report in archive["items"]}
    assert reports, "No daily reports exist; run and verify the actual n8n daily workflow first"
    assert archive["retention_entries"] == 31 and len(reports) <= 31
    assert all(key.startswith("n8n-daily:") for key in reports)
    assert all(report["source"] == "demo" and report["summary"]["source"] == "demo"
               for report in archive["items"])
    devices = {item["id"]: item for item in snapshot["devices"]}
    assert len(devices) == 7 and all(item["source"] == "demo" for item in devices.values())
    assert all(devices[device_id]["is_stale"] for device_id in STALE_IDS)
    decisions = {item["id"]: digest(item) for item in evidence["items"]
                 if item["status"] in {"approved", "rejected"}}
    assert decisions, "No existing operator decision is available for persistence verification"
    assert all(item["incident_published"] is False for item in evidence["items"])
    return {
        "reports": reports,
        "decisions": decisions,
        "stale_timestamps": {key: devices[key]["reported_at"] for key in sorted(STALE_IDS)},
        "stale_alert_ids": {item["device_id"]: item["id"] for item in snapshot["alerts"]
                            if item["status"] == "open" and item["device_id"] in STALE_IDS},
        "automation_run_count": snapshot["automation"]["run_count"],
    }


def retained(before, after):
    for key, value in before["reports"].items():
        assert after["reports"].get(key) == value, "A daily report was lost or changed"
    for key, value in before["decisions"].items():
        assert after["decisions"].get(key) == value, "An operator evidence decision was lost or changed"
    assert after["stale_timestamps"] == before["stale_timestamps"], "A stale source timestamp was refreshed"
    assert after["stale_alert_ids"] == before["stale_alert_ids"], "Existing stale alerts were replaced"
    assert after["automation_run_count"] >= before["automation_run_count"]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("capture", "verify"))
    mode = parser.parse_args().mode
    account = json.loads((ROOT / "accounts.json").read_text())["roadsignal"]
    login = request(API + "/api/v1/auth/login", account)
    headers = {"Authorization": "Bearer " + login["access_token"]}
    try:
        request(API + "/api/v1/monitoring/reports")
        raise AssertionError("Daily archive accepted an unauthenticated request")
    except HTTPError as error:
        assert error.code == 401, "Daily archive must require operator authentication"
    state = read_state(headers)
    if mode == "verify":
        retained(json.loads(BASELINE.read_text()), state)
    internal = {"Authorization": "Bearer " + (ROOT / "monitoring-token").read_text().strip()}
    result = request(N8N + "/webhook/roadsignal-device-health", {}, internal)
    if isinstance(result, list):
        result = result[0]
    assert result["run_key"].startswith("n8n-health:"), "Expected the real n8n health workflow response"
    after = read_state(headers)
    retained(state, after)
    if mode == "capture":
        save(BASELINE, json.dumps(after), mode=0o600)
    print(json.dumps({"result": "passed", "mode": mode,
                      "daily_reports": len(after["reports"]),
                      "report_keys": sorted(after["reports"]),
                      "preserved_decisions": len(after["decisions"]),
                      "preserved_stale_devices": len(after["stale_timestamps"]),
                      "health_webhook": "n8n-authenticated",
                      "daily_reports_created_by_this_check": 0,
                      "source": "demo"}))


if __name__ == "__main__":
    main()
