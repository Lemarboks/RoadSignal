"""Exercise the deployed route API; never print private operator credentials."""

import json
import os
from datetime import datetime, timezone
from urllib.request import Request, urlopen

from bootstrap import ROOT, request


def main():
    api = os.environ.get("API_URL", "http://api:8000").rstrip("/")
    account = json.loads((ROOT / "accounts.json").read_text())["roadsignal"]
    login = request(api + "/api/v1/auth/login", account)
    payload = {
        "origin": "Cape Town City Hall, Cape Town",
        "destination": "Cape Town International Airport",
        "preference": "balanced",
        "vehicle_type": "car",
        "departure_time": datetime.now(timezone.utc).isoformat(),
    }
    req = Request(
        api + "/api/v1/routes/analyse",
        data=json.dumps(payload).encode(),
        headers={
            "Content-Type": "application/json",
            "Authorization": "Bearer " + login["access_token"],
        },
    )
    with urlopen(req, timeout=180) as response:
        result = json.load(response)
    assert result["provider"] == "valhalla", (
        "Expected the installed local Valhalla graph; API used " + result["provider"]
    )
    routes = result["routes"]
    assert routes and any(route["recommended"] for route in routes)
    assert all(route["id"].startswith("valhalla-route-") for route in routes)
    assert all(len(route["geometry"]) > 10 for route in routes)
    assert all(route["distance_km"] > 10 for route in routes)
    assert all(0 <= route["safety_score"] <= 100 for route in routes)
    print(json.dumps({
        "result": "passed",
        "provider": result["provider"],
        "routes": len(routes),
        "distance_km": [route["distance_km"] for route in routes],
        "geometry_points": [len(route["geometry"]) for route in routes],
        "safety_scores": "decision-support estimates, not verified safety",
    }))


if __name__ == "__main__":
    main()
