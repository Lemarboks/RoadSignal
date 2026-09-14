"""End-to-end local demo checks. Uses private credentials without printing them."""
import json
import os
import time
from urllib.error import HTTPError
from uuid import uuid4

from bootstrap import ROOT, request

API = os.environ.get("API_URL", "http://api:8000")
N8N = os.environ.get("N8N_URL", "http://n8n:5678")


def main():
    account = json.loads((ROOT / "accounts.json").read_text())["roadsignal"]
    login = request(API + "/api/v1/auth/login", account)
    user_headers = {"Authorization": "Bearer " + login["access_token"]}
    internal_headers = {"Authorization": "Bearer " + (ROOT / "monitoring-token").read_text().strip()}
    snapshot_url = API + "/api/v1/monitoring"
    first = request(snapshot_url, headers=user_headers)
    assert len(first["devices"]) == 7, "Expected 4 GPS trackers and 3 sensor stations"
    assert all(device["source"] == "demo" for device in first["devices"])
    time.sleep(7)
    second = request(snapshot_url, headers=user_headers)
    a = {device["id"]: device for device in first["devices"]}
    b = {device["id"]: device for device in second["devices"]}
    assert b["CA 482-771"]["reported_at"] > a["CA 482-771"]["reported_at"], "GPS not refreshing"
    assert b["S1"]["reported_at"] > a["S1"]["reported_at"], "Sensor not refreshing"
    assert b["CA 614-208"]["is_stale"] and b["S3"]["is_stale"]
    assert b["CA 614-208"]["reported_at"] == a["CA 614-208"]["reported_at"]
    print("PASS: seven upstream-backed demo devices; live refresh and retained stale timestamps")
    try:
        request(N8N + "/webhook/roadsignal-device-health", {})
        raise AssertionError("Unauthenticated n8n webhook was accepted")
    except HTTPError as error:
        assert error.code in {401, 403}, "n8n must reject unauthenticated webhook requests"
    request(N8N + "/webhook/roadsignal-device-health", {}, internal_headers)
    checked = request(snapshot_url, headers=user_headers)
    assert checked["automation"]["last_run_key"].startswith("n8n-")
    assert {alert["device_id"] for alert in checked["alerts"] if alert["status"] == "open"} == {"CA 614-208", "S3"}
    request(N8N + "/webhook/roadsignal-device-health", {}, internal_headers)
    repeated = request(snapshot_url, headers=user_headers)
    assert len([alert for alert in repeated["alerts"] if alert["status"] == "open"]) == 2
    print("PASS: authenticated n8n execution, expected alerts and retry deduplication")
    event_id = "demo-smoke-" + uuid4().hex
    body = {"event_id": event_id, "source": "demo", "claim": "The demonstration road is closed.",
            "evidence": [{"text": "The demonstration road is closed for maintenance.", "source_url": "https://example.com/synthetic-evidence"}]}
    before = request(API + "/api/v1/incidents")
    # Model inference may take longer than the generic short request helper.
    result = request(N8N + "/webhook/roadsignal-evidence", body, internal_headers)
    if isinstance(result, list):
        result = result[0]
    assert result["status"] == "pending" and result["incident_published"] is False
    assert result["analysis"].get("assessment") == "textual_consistency_only", "Evidence workflow did not run real NLI"
    decision = request(API + f"/api/v1/monitoring/evidence/{result['id']}/decision",
                       {"decision": "approved", "note": "Synthetic end-to-end test only; not a real incident."}, user_headers)
    assert decision["incident_published"] is False and decision["reviewed_by"]
    after = request(API + "/api/v1/incidents")
    assert before == after, "Evidence review must not mutate road incidents"
    # Leave one clearly labelled, idempotent example in the inbox for showcasing.
    body["event_id"] = "roadsignal-showcase-example-v1"
    try:
        request(N8N + "/webhook/roadsignal-evidence", body, internal_headers)
    except HTTPError as error:
        if error.code != 409:
            raise
    print("PASS: n8n -> real NLI -> persistent operator review; incident state unchanged")
    print(json.dumps({"result": "passed", "devices": 7, "expected_stale": 2,
                      "n8n_run_count": repeated["automation"]["run_count"], "data_source": "demo"}))


if __name__ == "__main__":
    main()
