"""Initialize local-only integration accounts. Never print credentials by default.

Generated state belongs in Docker volumes, never source control. Re-running init
preserves every existing secret; provision only touches RoadSignal demo devices.
"""
import base64
import json
import os
from pathlib import Path
import secrets
import sys
from urllib.error import HTTPError
from urllib.request import Request, urlopen

ROOT = Path(os.environ.get("INTEGRATION_SECRETS", "/run/roadsignal"))


def request(url, body=None, headers=None, method=None):
    data = None if body is None else json.dumps(body).encode()
    req = Request(url, data=data, headers={"Content-Type": "application/json", **(headers or {})}, method=method)
    with urlopen(req, timeout=30) as response:
        raw = response.read(2_000_000)
        return json.loads(raw) if raw else None


def basic(email, password):
    encoded = base64.b64encode(f"{email}:{password}".encode()).decode()
    return {"Authorization": f"Basic {encoded}"}


def save(path, value, uid=0, gid=0, mode=0o640):
    path.write_text(value, encoding="utf-8")
    path.chmod(mode)
    if hasattr(os, "chown"):
        os.chown(path, uid, gid)


def init():
    ROOT.mkdir(parents=True, exist_ok=True)
    ROOT.chmod(0o755)
    for name, uid, gid in [("monitoring-token", 10001, 10001), ("thingsboard-db-password", 0, 0)]:
        path = ROOT / name
        if not path.exists():
            save(path, secrets.token_urlsafe(48), uid, gid)
    account_path = ROOT / "accounts.json"
    if not account_path.exists():
        save(account_path, json.dumps({
            "traccar": {"email": "operator@roadsignal.local", "password": secrets.token_urlsafe(24)},
            "thingsboard": {name: secrets.token_urlsafe(24) for name in ("sysadmin", "tenant", "customer")},
        }), mode=0o600)
    accounts = json.loads(account_path.read_text())
    for application in ("n8n", "roadsignal"):
        if application not in accounts:
            accounts[application] = {"email": "operator@roadsignal.local", "password": "Rs9!" + secrets.token_urlsafe(24)}
    save(account_path, json.dumps(accounts), mode=0o600)
    # Java image UID differs between releases; only this DB config is world-readable
    # inside the specifically mounted volume. It is never exposed on a host port.
    save(ROOT / "thingsboard.properties", "spring.datasource.password=" + (ROOT / "thingsboard-db-password").read_text() + "\n", mode=0o644)
    imports = Path("/n8n-import")
    imports.mkdir(parents=True, exist_ok=True)
    token = (ROOT / "monitoring-token").read_text().strip()
    credential = [{"id": "roadsignal-internal", "name": "RoadSignal local automation", "type": "httpHeaderAuth",
                   "data": {"name": "Authorization", "value": f"Bearer {token}"}}]
    save(imports / "credentials.json", json.dumps(credential), 1000, 1000, 0o600)
    print("Integration secrets ready; existing keys preserved. No secrets printed.")


def provision_traccar():
    accounts = json.loads((ROOT / "accounts.json").read_text())
    account = accounts["traccar"]
    base = os.environ.get("TRACCAR_URL", "http://traccar:8082")
    headers = basic(account["email"], account["password"])
    try:
        devices = request(base + "/api/devices", headers=headers)
    except HTTPError as error:
        if error.code != 401:
            raise
        request(base + "/api/users", {"name": "RoadSignal demo operator", **account})
        devices = request(base + "/api/devices", headers=headers)
    by_unique = {item["uniqueId"]: item for item in devices}
    mapping = {}
    for index, plate in enumerate(["CA 482-771", "CA 193-044", "CY 827-519", "CA 614-208"], start=1):
        unique = f"roadsignal-demo-v{index}"
        device = by_unique.get(unique)
        if not device:
            device = request(base + "/api/devices", {"name": f"DEMO {plate}", "uniqueId": unique,
                             "category": "car", "attributes": {"source": "demo", "roadsignalId": plate}}, headers)
        mapping[plate] = {"id": device["id"], "uniqueId": unique}
    save(ROOT / "traccar-devices.json", json.dumps(mapping), mode=0o600)
    print(f"Traccar ready: {len(mapping)} explicitly labelled demo trackers.")


def tb_login(base, name, password):
    data = request(base + "/api/auth/login", {"username": f"{name}@thingsboard.org", "password": password})
    return {"X-Authorization": "Bearer " + data["token"]}


def provision_n8n():
    base = os.environ.get("N8N_URL", "http://n8n:5678")
    account = json.loads((ROOT / "accounts.json").read_text())["n8n"]
    settings = request(base + "/rest/settings")
    management = settings.get("data", settings).get("userManagement", {})
    if management.get("showSetupOnFirstLoad"):
        request(base + "/rest/owner/setup", {**account, "firstName": "RoadSignal", "lastName": "Operator"})
        print("n8n local owner configured; credentials stored privately.")
    else:
        print("n8n owner already configured; existing account preserved.")


def provision_thingsboard():
    base = os.environ.get("THINGSBOARD_URL", "http://thingsboard:8080")
    accounts = json.loads((ROOT / "accounts.json").read_text())["thingsboard"]
    # Rotate all built-in demo passwords before local showcase use.
    for name, password in accounts.items():
        try:
            tb_login(base, name, password)
        except HTTPError as error:
            if error.code != 401:
                raise
            headers = tb_login(base, name, name)
            request(base + "/api/auth/changePassword", {"currentPassword": name, "newPassword": password}, headers)
    headers = tb_login(base, "tenant", accounts["tenant"])
    existing = request(base + "/api/tenant/devices?pageSize=100&page=0", headers=headers)["data"]
    by_name = {device["name"]: device for device in existing}
    mapping = {}
    for sid, location in [("S1", "Woodstock"), ("S2", "Athlone"), ("S3", "Airport approach")]:
        name = f"RoadSignal DEMO {sid} {location}"
        device = by_name.get(name) or request(base + "/api/device", {"name": name, "type": "RoadSignal simulated street sensor",
              "label": f"SIMULATED - {location}", "additionalInfo": {"description": "Synthetic readings, not real weather or traffic."}}, headers)
        did = device["id"]["id"]
        credentials = request(base + f"/api/device/{did}/credentials", headers=headers)
        mapping[sid] = {"id": did, "token": credentials["credentialsId"]}
        request(base + f"/api/plugins/telemetry/DEVICE/{did}/SERVER_SCOPE", {"source": "demo", "roadsignalId": sid}, headers)
    save(ROOT / "thingsboard-devices.json", json.dumps(mapping), mode=0o600)
    print(f"ThingsBoard ready: {len(mapping)} demo sensors; built-in passwords rotated.")


if __name__ == "__main__":
    action = sys.argv[1] if len(sys.argv) > 1 else "init"
    if action == "init":
        init()
    elif action == "traccar":
        provision_traccar()
    elif action == "thingsboard":
        provision_thingsboard()
    elif action == "n8n":
        provision_n8n()
    elif action == "credentials":
        # Explicit local operator command only; never called during automated setup.
        print((ROOT / "accounts.json").read_text())
    elif action == "imports-state":
        print("done" if (ROOT / "n8n-imported-v1").exists() else "pending")
    elif action == "mark-imported":
        save(ROOT / "n8n-imported-v1", "completed\n", mode=0o600)
    else:
        raise SystemExit("Use init, traccar, thingsboard or credentials")
