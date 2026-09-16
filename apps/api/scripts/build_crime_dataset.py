"""Build a compact per-precinct crime dataset from published SAPS statistics.

Source data (both public domain / open):
  * afrith/crime-stats -- monthly SAPS crime counts per police station
    (Jan 2020 - Sep 2025) plus Stats SA police district boundaries, released
    under the Open Data Commons PDDL v1.0.
  * Boundaries arrive as a GeoPackage, which is just SQLite, so this reads it
    with the standard library instead of pulling in geopandas/fiona. Keeping
    the API installable without heavy geo dependencies matters more here than
    the convenience.

The upstream crime CSV is ~212MB, so it is streamed and filtered rather than
held in memory, and the result is a small committed JSON file. The API then
has no runtime dependency on a large download and works fully offline.

Usage:
    python apps/api/scripts/build_crime_dataset.py            # Cape Town
    python apps/api/scripts/build_crime_dataset.py --muni JHB
"""
from __future__ import annotations

import argparse
import csv
import io
import json
import sqlite3
import struct
import sys
import urllib.request
from collections import defaultdict
from pathlib import Path

STATIONS_GPKG = "https://media.githubusercontent.com/media/afrith/crime-stats/main/police_stations.gpkg"
CRIME_CSV = "https://media.githubusercontent.com/media/afrith/crime-stats/main/crime-stats.csv"

# Crimes a driver is actually exposed to on the road: the vehicle itself being
# taken, broken into, or the occupant robbed. Deliberately excludes the many
# categories that say nothing about road risk (shoplifting, domestic offences,
# commercial crime), so the score reflects driving exposure rather than a
# general "bad area" judgement.
VEHICLE_CRIME_WEIGHTS = {
    34: ("Carjacking", 3.0),
    35: ("Truck hijacking", 2.0),
    4: ("Robbery with aggravating circumstances", 1.5),
    24: ("Theft of motor vehicle and motorcycle", 1.0),
    25: ("Theft out of or from motor vehicle", 0.8),
    6: ("Common robbery", 0.6),
}
MONTHS_WINDOW = 12

# Map the weighted per-100k rate onto a baseline penalty comparable to the
# hand-tuned values the risk engine already used for its crime channel
# (roughly 5-18), so introducing real data does not rescale every score.
BASELINE_MIN, BASELINE_MAX = 4.0, 26.0


def fetch(url: str, dest: Path) -> Path:
    if dest.exists() and dest.stat().st_size > 0:
        print(f"  reusing cached {dest.name} ({dest.stat().st_size/1e6:.1f}MB)")
        return dest
    print(f"  downloading {url.rsplit('/', 1)[-1]} ...")
    req = urllib.request.Request(url, headers={"User-Agent": "RoadSignal/1.0 (crime dataset build)"})
    with urllib.request.urlopen(req, timeout=600) as response, dest.open("wb") as handle:
        while chunk := response.read(1 << 20):
            handle.write(chunk)
    print(f"  saved {dest.name} ({dest.stat().st_size/1e6:.1f}MB)")
    return dest


# --- GeoPackage geometry (GPB header + standard WKB) ------------------------

def gpb_to_wkb(blob: bytes) -> bytes:
    if blob[:2] != b"GP":
        raise ValueError("not a GeoPackage geometry blob")
    envelope_kind = (blob[3] >> 1) & 0x07
    doubles = {0: 0, 1: 4, 2: 6, 3: 6, 4: 8}[envelope_kind]
    return blob[8 + doubles * 8:]


def parse_wkb_polygons(wkb: bytes) -> list[list[tuple[float, float]]]:
    pos = 0

    def u8() -> int:
        nonlocal pos
        value = wkb[pos]; pos += 1; return value

    def u32(little: bool) -> int:
        nonlocal pos
        value = struct.unpack_from("<I" if little else ">I", wkb, pos)[0]; pos += 4; return value

    def pair(little: bool) -> tuple[float, float]:
        nonlocal pos
        x, y = struct.unpack_from("<dd" if little else ">dd", wkb, pos); pos += 16
        return (x, y)

    def polygon(little: bool) -> list[list[tuple[float, float]]]:
        return [[pair(little) for _ in range(u32(little))] for _ in range(u32(little))]

    little = u8() == 1
    geometry_type = u32(little) % 1000
    if geometry_type == 3:
        return polygon(little)
    if geometry_type == 6:
        rings: list[list[tuple[float, float]]] = []
        for _ in range(u32(little)):
            inner_little = u8() == 1
            u32(inner_little)
            rings.extend(polygon(inner_little))
        return rings
    raise ValueError(f"unsupported WKB geometry type {geometry_type}")


def simplify(ring: list[tuple[float, float]], tolerance: float) -> list[tuple[float, float]]:
    """Douglas-Peucker. Precinct outlines only need enough detail to place a
    route point; full Stats SA resolution would bloat the committed file.

    Closed rings need care: when the first and last vertex are identical the
    perpendicular-distance numerator collapses to zero for every candidate, so
    a naive implementation reports "nothing exceeds the tolerance" and returns
    a degenerate two-point ring. The ring is therefore opened (closing vertex
    dropped), split at the vertex furthest from the start so neither half is
    degenerate, simplified, then re-closed.
    """
    if len(ring) < 5:
        return ring

    def reduce(points: list[tuple[float, float]]) -> list[tuple[float, float]]:
        if len(points) < 3:
            return points
        (x1, y1), (x2, y2) = points[0], points[-1]
        dx, dy = x2 - x1, y2 - y1
        norm = (dx * dx + dy * dy) ** 0.5
        worst, index = -1.0, 0
        for i in range(1, len(points) - 1):
            x0, y0 = points[i]
            if norm < 1e-12:  # degenerate segment: fall back to point distance
                distance = ((x0 - x1) ** 2 + (y0 - y1) ** 2) ** 0.5
            else:
                distance = abs(dy * x0 - dx * y0 + x2 * y1 - y2 * x1) / norm
            if distance > worst:
                worst, index = distance, i
        if worst <= tolerance or index == 0:
            return [points[0], points[-1]]
        return reduce(points[: index + 1])[:-1] + reduce(points[index:])

    sys.setrecursionlimit(10000)
    closed = ring[0] == ring[-1]
    open_ring = ring[:-1] if closed else list(ring)
    # Split at the vertex furthest from the start so each half has distinct ends.
    x0, y0 = open_ring[0]
    far = max(range(1, len(open_ring)), key=lambda i: (open_ring[i][0] - x0) ** 2 + (open_ring[i][1] - y0) ** 2)
    out = reduce(open_ring[: far + 1])[:-1] + reduce(open_ring[far:])
    if len(out) < 4:  # simplification destroyed it; keep the original outline
        return ring
    if closed and out[0] != out[-1]:
        out.append(out[0])
    return out


def load_precincts(gpkg: Path, muni: str) -> dict[str, dict]:
    con = sqlite3.connect(gpkg)
    rows = con.execute(
        "select code, name, population, area_km2, geom from police_stations where muni_code = ?",
        (muni,),
    ).fetchall()
    con.close()
    precincts: dict[str, dict] = {}
    for code, name, population, area_km2, blob in rows:
        rings = parse_wkb_polygons(gpb_to_wkb(blob))
        rings = [simplify(ring, 0.0004) for ring in rings]  # ~40m
        precincts[code] = {
            "code": code,
            "name": name,
            "population": int(population or 0),
            "area_km2": round(float(area_km2 or 0), 2),
            "rings": [[[round(x, 5), round(y, 5)] for x, y in ring] for ring in rings],
        }
    return precincts


def aggregate_crime(csv_path: Path, codes: set[str]) -> tuple[dict[str, dict[str, float]], str]:
    """Weighted vehicle-crime counts over the most recent MONTHS_WINDOW months."""
    periods: set[tuple[int, int]] = set()
    per_station: dict[str, dict[tuple[int, int], dict[int, int]]] = defaultdict(lambda: defaultdict(dict))

    with csv_path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.reader(handle)
        next(reader, None)
        for row in reader:
            if len(row) < 8 or row[1] not in codes:
                continue
            try:
                crime_code, year, month, count = int(row[3]), int(row[5]), int(row[6]), int(row[7])
            except ValueError:
                continue
            if crime_code not in VEHICLE_CRIME_WEIGHTS:
                continue
            periods.add((year, month))
            per_station[row[1]][(year, month)][crime_code] = count

    recent = sorted(periods)[-MONTHS_WINDOW:]
    if not recent:
        raise SystemExit("no crime rows matched the requested precincts")
    window = f"{recent[0][0]}-{recent[0][1]:02d} to {recent[-1][0]}-{recent[-1][1]:02d}"

    totals: dict[str, dict[str, float]] = {}
    for code, by_period in per_station.items():
        weighted = 0.0
        breakdown: dict[str, int] = defaultdict(int)
        for period in recent:
            for crime_code, count in by_period.get(period, {}).items():
                label, weight = VEHICLE_CRIME_WEIGHTS[crime_code]
                weighted += count * weight
                breakdown[label] += count
        totals[code] = {"weighted": weighted, "breakdown": dict(breakdown)}
    return totals, window


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--muni", default="CPT", help="Stats SA municipality code (default CPT)")
    parser.add_argument("--cache", default=None, help="directory for the large downloads")
    parser.add_argument(
        "--out",
        default=str(Path(__file__).resolve().parents[1] / "app" / "data" / "crime_precincts.json"),
    )
    args = parser.parse_args()

    cache = Path(args.cache) if args.cache else Path(__file__).resolve().parents[3] / ".crime-cache"
    cache.mkdir(parents=True, exist_ok=True)

    print("fetching source data")
    gpkg = fetch(STATIONS_GPKG, cache / "police_stations.gpkg")
    crime_csv = fetch(CRIME_CSV, cache / "crime-stats.csv")

    print(f"reading precinct boundaries for muni={args.muni}")
    precincts = load_precincts(gpkg, args.muni)
    print(f"  {len(precincts)} precincts")

    # Guard: a simplification bug once collapsed every ring to two identical
    # vertices, which still produced a plausible-looking file. Fail loudly.
    degenerate = [p["name"] for p in precincts.values() if sum(len(r) for r in p["rings"]) < 4]
    if degenerate:
        raise SystemExit(f"degenerate geometry for {len(degenerate)} precincts: {degenerate[:5]}")
    vertices = sum(len(r) for p in precincts.values() for r in p["rings"])
    print(f"  {vertices} vertices after simplification ({vertices / len(precincts):.0f} per precinct)")

    print("aggregating vehicle-directed crime")
    totals, window = aggregate_crime(crime_csv, set(precincts))
    print(f"  window: {window}")

    # A driver passing through cares how much vehicle crime happens in the area
    # they are driving through, not how many people live there. Per-resident
    # rates badly distort commercial precincts: the CBD has ~38k residents but
    # enormous daytime exposure, which produced a 10,000/100k outlier that
    # compressed every other precinct. Incident density per km2 is the better
    # denominator for road exposure. Per-capita is still recorded for context.
    density: dict[str, float] = {}
    per_capita: dict[str, float] = {}
    for code, precinct in precincts.items():
        weighted = totals.get(code, {}).get("weighted", 0.0)
        area = precinct["area_km2"] or 0.0
        population = precinct["population"]
        density[code] = (weighted / area) if area > 0 else 0.0
        per_capita[code] = (weighted / population * 100_000) if population > 0 else 0.0

    # Percentile rank rather than min-max: robust to the single extreme
    # precinct, and gives an even spread across the engine's baseline range.
    ordered = sorted(density.values())

    def percentile_of(value: float) -> float:
        if len(ordered) < 2:
            return 0.5
        below = sum(1 for other in ordered if other < value)
        equal = sum(1 for other in ordered if other == value)
        return (below + equal / 2) / len(ordered)

    features = []
    for code, precinct in precincts.items():
        rank = percentile_of(density[code])
        baseline = BASELINE_MIN + rank * (BASELINE_MAX - BASELINE_MIN)
        features.append({
            **precinct,
            "weighted_incidents": round(totals.get(code, {}).get("weighted", 0.0), 1),
            "per_km2": round(density[code], 1),
            "rate_per_100k": round(per_capita[code], 1),
            "percentile": round(rank, 3),
            "crime_baseline": round(max(BASELINE_MIN, min(BASELINE_MAX, baseline)), 2),
            "breakdown": totals.get(code, {}).get("breakdown", {}),
        })
    features.sort(key=lambda item: item["per_km2"], reverse=True)

    payload = {
        "source": "SAPS quarterly crime statistics via afrith/crime-stats (PDDL v1.0); boundaries from Stats SA",
        "municipality": args.muni,
        "window": window,
        "months": MONTHS_WINDOW,
        "categories": {str(k): v[0] for k, v in VEHICLE_CRIME_WEIGHTS.items()},
        "category_weights": {v[0]: v[1] for v in VEHICLE_CRIME_WEIGHTS.values()},
        "baseline_range": [BASELINE_MIN, BASELINE_MAX],
        "density_range": [round(min(density.values()), 1), round(max(density.values()), 1)],
        "precincts": features,
    }

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, separators=(",", ":")), encoding="utf-8")
    print(f"wrote {out} ({out.stat().st_size/1024:.0f}KB)")
    print("\nhighest vehicle-crime precincts:")
    for item in features[:8]:
        print(f"  {item['name']:24} {item['rate_per_100k']:8.1f}/100k  baseline={item['crime_baseline']:.1f}")


if __name__ == "__main__":
    main()
