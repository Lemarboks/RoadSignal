"""Build the crash-history dataset from City of Cape Town open data.

Why this exists: the risk engine has an "accident" channel weighted at 0.25
that, until now, only responded to user-reported incidents -- it had no
baseline at all. So a road with six years of fatal crashes scored identically
to a quiet suburban street until somebody happened to report something.

The City publishes 377,996 crash records for 2019-2024 with road description,
police station, weekday, time, crash type, alleged cause, and casualty counts
split by severity. Their terms make the data available "without any
remuneration" on an "as is" basis, with no attribution requirement and no
stated restriction on reuse; we credit them anyway.

The source table has no geometry, so crashes are joined to the SAPS precinct
polygons already shipped for the crime layer via POLICE_STATION. That join is
the reason this is cheap: the point-in-polygon machinery already exists.

Aggregation happens server-side (groupByFieldsForStatistics), so this pulls a
few hundred rows rather than 378k records.

Usage:
    python scripts/build_crash_dataset.py            # writes app/data/crash_history.json
    python scripts/build_crash_dataset.py --dry-run  # report only, write nothing
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

SERVICE = (
    "https://services6.arcgis.com/nyYfO9SxHU2ChQd9/arcgis/rest/services/"
    "Crash_Data_Statistics_2019_to_2024/FeatureServer/0/query"
)
SOURCE_LABEL = (
    "City of Cape Town Open Data Portal - Traffic Accidents (Crash Data) "
    "Statistics 2019 to 2024"
)
WINDOW = "2019 to 2024"

PRECINCTS_PATH = Path(__file__).resolve().parents[1] / "app" / "data" / "crime_precincts.json"
OUTPUT_PATH = Path(__file__).resolve().parents[1] / "app" / "data" / "crash_history.json"

# Driver-meaningful time bands rather than even slices: the morning and evening
# peaks are the periods a departure time actually lands in. Bands are unequal
# lengths, so slot comparisons must use crashes per hour -- otherwise a wide
# band looks more dangerous purely for being wide.
BANDS: list[tuple[str, str, str | None]] = [
    ("late_night", "00:00:00", "06:00:00"),
    ("morning_peak", "06:00:00", "09:00:00"),
    ("midmorning", "09:00:00", "12:00:00"),
    ("afternoon", "12:00:00", "16:00:00"),
    ("evening_peak", "16:00:00", "19:00:00"),
    ("evening", "19:00:00", None),
]
BAND_HOURS = {
    "late_night": 6.0,
    "morning_peak": 3.0,
    "midmorning": 3.0,
    "afternoon": 4.0,
    "evening_peak": 3.0,
    "evening": 5.0,
}
WEEKDAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]

# Spelling variants in the source that refer to a precinct we already map.
# Only genuine spelling differences belong here -- a traffic division such as
# "DIV8 BLAAUWBERG TRAFFIC" is not a precinct and must not be forced into one.
ALIASES = {
    "PHILLIPIEAST": "PHILIPPIEAST",
    "GUGULETU": "GUGULETHU",
    "LINGELETHUWEST": "LINGELETHUWEST",
    "MITCHELLSPLAIN": "MITCHELLSPLAIN",
}

# A fatal crash is not one unit of harm. Road-safety costing puts a fatality
# one to two orders of magnitude above property damage; these weights are
# deliberately moderate so one tragedy cannot swamp a precinct's whole score.
CASUALTY_WEIGHTS = {"fatal": 12.0, "serious": 4.0, "slight": 1.0}

BASELINE_MIN, BASELINE_MAX = 4.0, 26.0  # matches the crime layer's scale
MIN_SLOT_SAMPLE = 20  # below this a slot multiplier is not trustworthy
SLOT_MULTIPLIER_RANGE = (0.6, 2.2)
MIN_JOIN_RATE = 0.85  # guard: refuse to ship a dataset that mostly failed to join


def normalise(name: str | None) -> str:
    """Reduce a station name to a comparable key.

    The source mixes casing and suffixes freely: "CAMPS BAY SAPS",
    "Sea Point Saps", "Harare", "Bellville Traffic".
    """
    text = (name or "").upper().strip()
    text = re.sub(r"\s+(SAPS|SAP|TRAFFIC|TRAFFIC DEPT|TRAFFIC DEPARTMENT|SATELLITE)$", "", text)
    key = re.sub(r"[^A-Z]", "", text)
    return ALIASES.get(key, key)


def fetch(params: dict) -> dict:
    query = urllib.parse.urlencode({**params, "f": "json"})
    request = urllib.request.Request(
        f"{SERVICE}?{query}",
        headers={"User-Agent": "RoadSignal/1.0 crash dataset builder"},
    )
    with urllib.request.urlopen(request, timeout=120) as response:
        return json.loads(response.read().decode("utf-8"))


def grouped(where: str) -> list[dict]:
    """All groups for a filter, following ArcGIS transfer-limit paging."""
    statistics = [
        {"statisticType": "count", "onStatisticField": "ObjectId", "outStatisticFieldName": "n"},
        {"statisticType": "sum", "onStatisticField": "FATAL", "outStatisticFieldName": "fatal"},
        {"statisticType": "sum", "onStatisticField": "SERIOUS", "outStatisticFieldName": "serious"},
        {"statisticType": "sum", "onStatisticField": "SLIGHT", "outStatisticFieldName": "slight"},
        {
            "statisticType": "sum",
            "onStatisticField": "PEDESTRIANS",
            "outStatisticFieldName": "pedestrians",
        },
    ]
    rows: list[dict] = []
    offset = 0
    while True:
        payload = fetch(
            {
                "where": where,
                "groupByFieldsForStatistics": "POLICE_STATION,WKDAY",
                "outStatistics": json.dumps(statistics),
                "resultOffset": offset,
                "resultRecordCount": 1000,
            }
        )
        if "error" in payload:
            raise SystemExit(f"ArcGIS error for where={where!r}: {payload['error']}")
        features = payload.get("features", [])
        rows.extend(feature["attributes"] for feature in features)
        if not payload.get("exceededTransferLimit") or not features:
            return rows
        offset += len(features)


def weighted_harm(row: dict) -> float:
    """Crash count plus casualty severity, so outcome shapes the score."""
    total = float(row.get("n") or 0)
    for field, weight in CASUALTY_WEIGHTS.items():
        total += weight * float(row.get(field) or 0)
    return total


def percentile_ranks(values: dict[str, float]) -> dict[str, float]:
    """Rank each key against the others, 0..1.

    Ranking rather than scaling by magnitude: an earlier version of the crime
    dataset scaled by raw rate and one extreme precinct compressed every other
    score into a narrow band at the bottom.
    """
    ordered = sorted(values.values())
    if len(ordered) < 2:
        return {key: 0.5 for key in values}
    ranks = {}
    for key, value in values.items():
        below = sum(1 for other in ordered if other < value)
        equal = sum(1 for other in ordered if other == value)
        ranks[key] = (below + 0.5 * equal) / len(ordered)
    return ranks


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="report without writing")
    args = parser.parse_args()

    precincts = json.loads(PRECINCTS_PATH.read_text(encoding="utf-8"))["precincts"]
    by_key = {normalise(precinct["name"]): precinct for precinct in precincts}
    print(f"precinct polygons available: {len(by_key)}")

    # Per band, per precinct, per weekday.
    slots: dict[str, dict[str, dict[str, float]]] = {}
    totals: dict[str, dict[str, float]] = {}
    unmapped: dict[str, float] = {}
    joined = seen = 0

    for band, start, end in BANDS:
        where = f"TIME >= '{start}'" + (f" AND TIME < '{end}'" if end else "")
        rows = grouped(where)
        band_total = sum(float(row.get("n") or 0) for row in rows)
        print(f"  {band:<13} {int(band_total):>7,} crashes across {len(rows)} groups")
        for row in rows:
            count = float(row.get("n") or 0)
            seen += count
            key = normalise(row.get("POLICE_STATION"))
            if key not in by_key:
                unmapped[row.get("POLICE_STATION") or "?"] = (
                    unmapped.get(row.get("POLICE_STATION") or "?", 0) + count
                )
                continue
            joined += count
            name = by_key[key]["name"]
            harm = weighted_harm(row)
            bucket = totals.setdefault(
                name, {"crashes": 0.0, "fatal": 0.0, "serious": 0.0, "slight": 0.0,
                       "pedestrians": 0.0, "harm": 0.0}
            )
            bucket["crashes"] += count
            bucket["harm"] += harm
            for field in ("fatal", "serious", "slight", "pedestrians"):
                bucket[field] += float(row.get(field) or 0)
            weekday = row.get("WKDAY")
            if weekday in WEEKDAYS:
                slots.setdefault(name, {}).setdefault(f"{weekday}|{band}", {"n": 0.0})["n"] += count

    join_rate = joined / seen if seen else 0.0
    print(f"\njoined {int(joined):,} of {int(seen):,} crashes ({join_rate:.1%})")
    if join_rate < MIN_JOIN_RATE:
        print(f"REFUSING to write: join rate below {MIN_JOIN_RATE:.0%}.", file=sys.stderr)
        print("A dataset that mostly failed to join looks plausible and is wrong.", file=sys.stderr)
        return 1

    density = {
        name: bucket["harm"] / max(0.01, float(by_key[normalise(name)]["area_km2"]))
        for name, bucket in totals.items()
    }
    ranks = percentile_ranks(density)

    output_precincts = {}
    for name, bucket in sorted(totals.items()):
        rank = ranks[name]
        baseline = BASELINE_MIN + (BASELINE_MAX - BASELINE_MIN) * rank
        # A slot multiplier compares one weekday/band against this precinct's
        # own average, so it expresses "worse than usual here" rather than
        # re-stating that busy precincts are busy. Rates are per hour: the
        # bands are unequal lengths, and comparing raw counts would rate a
        # 6-hour band above a 3-hour one on width alone.
        precinct_slots = slots.get(name, {})
        rates = {
            slot: value["n"] / BAND_HOURS[slot.split("|", 1)[1]]
            for slot, value in precinct_slots.items()
        }
        average = sum(rates.values()) / len(rates) if rates else 0.0
        multipliers = {}
        for slot, value in sorted(precinct_slots.items()):
            if value["n"] < MIN_SLOT_SAMPLE or average <= 0:
                continue
            ratio = rates[slot] / average
            clamped = max(SLOT_MULTIPLIER_RANGE[0], min(SLOT_MULTIPLIER_RANGE[1], ratio))
            multipliers[slot] = round(clamped, 3)
        output_precincts[name] = {
            "crashes": int(bucket["crashes"]),
            "fatal": int(bucket["fatal"]),
            "serious": int(bucket["serious"]),
            "slight": int(bucket["slight"]),
            "pedestrians": int(bucket["pedestrians"]),
            "harm_per_km2": round(density[name], 2),
            "percentile": round(rank, 3),
            "accident_baseline": round(baseline, 2),
            "slot_multipliers": multipliers,
        }

    dataset = {
        "source": SOURCE_LABEL,
        "source_terms": 'Provided "without any remuneration" on an "as is" basis; '
                        "the City makes no warranty as to accuracy or completeness.",
        "municipality": "CPT",
        "window": WINDOW,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "joined_crashes": int(joined),
        "total_crashes": int(seen),
        "join_rate": round(join_rate, 4),
        "casualty_weights": CASUALTY_WEIGHTS,
        "baseline_range": [BASELINE_MIN, BASELINE_MAX],
        "bands": {band: [start, end or "24:00:00"] for band, start, end in BANDS},
        "min_slot_sample": MIN_SLOT_SAMPLE,
        # Recorded rather than hidden: these are traffic divisions and stations
        # outside the mapped precincts, so their crashes are genuinely
        # unplaceable rather than quietly dropped.
        "unmapped_groups": {
            name: int(count)
            for name, count in sorted(unmapped.items(), key=lambda item: -item[1])
        },
        "precincts": output_precincts,
    }

    baselines = [p["accident_baseline"] for p in output_precincts.values()]
    print(f"precincts with crash history: {len(output_precincts)}")
    print(f"accident_baseline range     : {min(baselines):.2f} -> {max(baselines):.2f}")
    worst = max(output_precincts.items(), key=lambda item: item[1]["accident_baseline"])
    print(f"highest                     : {worst[0]} "
          f"({worst[1]['crashes']:,} crashes, {worst[1]['fatal']} fatal)")

    if args.dry_run:
        print("\n--dry-run: nothing written")
        return 0
    OUTPUT_PATH.write_text(json.dumps(dataset, indent=1, sort_keys=False), encoding="utf-8")
    size_kb = OUTPUT_PATH.stat().st_size / 1024
    print(f"\nwrote {OUTPUT_PATH.relative_to(Path.cwd()) if OUTPUT_PATH.is_relative_to(Path.cwd()) else OUTPUT_PATH} ({size_kb:.0f} KB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
