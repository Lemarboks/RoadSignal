#!/usr/bin/env python3
"""Bounded staging smoke, security-header, and latency verifier."""

from __future__ import annotations

import argparse
import concurrent.futures
import json
import statistics
import ssl
import time
import urllib.error
import urllib.request
import urllib.parse
from pathlib import Path

REQUIRED_HEADERS = {
    "content-security-policy",
    "x-content-type-options",
    "x-frame-options",
    "referrer-policy",
    "permissions-policy",
}


def request(url: str, method: str = "GET", body: dict | None = None) -> tuple[int, float, dict[str, str], str]:
    encoded = json.dumps(body).encode() if body is not None else None
    headers = {"Accept": "application/json", "User-Agent": "RoadSignal-Staging-Readiness/1.0"}
    if encoded is not None:
        headers["Content-Type"] = "application/json"
    started = time.perf_counter()
    try:
        with urllib.request.urlopen(urllib.request.Request(url, encoded, headers, method=method), timeout=15) as response:
            return response.status, (time.perf_counter() - started) * 1000, dict(response.headers.items()), response.read().decode()
    except urllib.error.HTTPError as error:
        return error.code, (time.perf_counter() - started) * 1000, dict(error.headers.items()), error.read().decode()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--requests", type=int, default=60)
    parser.add_argument("--concurrency", type=int, default=6)
    parser.add_argument("--p95-ms", type=float, default=1500)
    parser.add_argument("--output", default="artifacts/staging-readiness.json")
    args = parser.parse_args()
    base = args.base_url.rstrip("/")
    parsed_base = urllib.parse.urlparse(base)
    local_http = parsed_base.scheme == "http" and parsed_base.hostname in {"localhost", "127.0.0.1"}
    if parsed_base.scheme != "https" and not local_http:
        parser.error("staging must use HTTPS (localhost is the only exception)")
    if not 1 <= args.requests <= 500 or not 1 <= args.concurrency <= 20:
        parser.error("requests must be 1-500 and concurrency 1-20")

    checks: list[dict] = []
    for path in ("/api/v1/health", "/api/v1/ready"):
        status, latency, headers, body = request(base + path)
        checks.append({"path": path, "status": status, "latency_ms": round(latency, 1)})
        if status != 200:
            raise SystemExit(f"{path} returned {status}: {body[:200]}")
        missing = REQUIRED_HEADERS - {name.lower() for name in headers}
        if missing:
            raise SystemExit(f"{path} is missing security headers: {sorted(missing)}")

    payload = {
        "origin": "Cape Town City Centre",
        "destination": "Cape Town International Airport",
        "preference": "balanced",
        "departure_time": "2026-08-23T12:00:00Z",
        "vehicle_type": "car",
    }
    warm_status, warm_latency, _, warm_body = request(base + "/api/v1/routes/analyse", "POST", payload)
    if warm_status != 200:
        raise SystemExit(f"route-analysis warm-up returned {warm_status}: {warm_body[:200]}")

    def sample(_: int) -> tuple[int, float]:
        status, latency, _, _ = request(base + "/api/v1/routes/analyse", "POST", payload)
        return status, latency

    with concurrent.futures.ThreadPoolExecutor(max_workers=args.concurrency) as pool:
        results = list(pool.map(sample, range(args.requests)))
    statuses = [status for status, _ in results]
    latencies = [latency for _, latency in results]
    failures = sum(status != 200 for status in statuses)
    ordered = sorted(latencies)
    p95 = ordered[max(0, round(0.95 * len(ordered)) - 1)]
    report = {
        "base_url": base,
        "generated_at_epoch": int(time.time()),
        "checks": checks,
        "load": {
            "requests": args.requests,
            "concurrency": args.concurrency,
            "failures": failures,
            "median_ms": round(statistics.median(latencies), 1),
            "p95_ms": round(p95, 1),
            "max_ms": round(max(latencies), 1),
            "threshold_ms": args.p95_ms,
            "warmup_ms": round(warm_latency, 1),
        },
    }
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    if failures or p95 > args.p95_ms:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
