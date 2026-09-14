from __future__ import annotations

import math
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any, Iterable

import h3


def utc_time(value: str | datetime) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00")) if isinstance(value, str) else value
    # MySQL DATETIME values are stored as UTC without an offset.
    return parsed.replace(tzinfo=timezone.utc) if parsed.tzinfo is None else parsed.astimezone(timezone.utc)


def incident_provenance(incident: dict[str, Any]) -> str:
    if "demo_sample" in (incident.get("abuse_flags") or []):
        return "demo"
    if incident.get("data_provenance") in {"demo", "reported"}:
        return incident["data_provenance"]
    if "community_report" in (incident.get("abuse_flags") or []):
        return "reported"
    # A legacy record's source_type does not establish whether it was seeded.
    return "unknown"


def combined_provenance(values: Iterable[str]) -> str:
    sources = set(values)
    return next(iter(sources)) if len(sources) == 1 else "mixed" if sources else "unknown"


def incident_cells(
    incidents: Iterable[dict[str, Any]], resolution: int = 7, *, now: datetime | None = None
) -> dict[str, Any]:
    """Return actual H3 polygons and summaries of current incident reports.

    Cell counts are evidence density, not estimated crime rates or safety scores.
    Sparse geographic aggregation does not establish anonymity.
    """
    if not 5 <= resolution <= 9:
        raise ValueError("Map resolution must be between 5 and 9")
    current = utc_time(now or datetime.now(timezone.utc))
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    excluded_invalid = 0
    for incident in incidents:
        if incident.get("status") != "active":
            continue
        try:
            occurred_at = utc_time(incident["occurred_at"])
            expires_at = utc_time(incident["expires_at"])
            if occurred_at > current or expires_at <= current:
                continue
            latitude = float(incident["location"]["latitude"])
            longitude = float(incident["location"]["longitude"])
            confidence = float(incident["confidence"])
            severity = float(incident["severity"])
            if not all(math.isfinite(value) for value in (latitude, longitude, confidence, severity)):
                raise ValueError("Non-finite incident values")
            if not (-90 <= latitude <= 90 and -180 <= longitude <= 180):
                raise ValueError("Invalid incident coordinates")
            if not (0 <= confidence <= 1 and 1 <= severity <= 5 and severity.is_integer()):
                raise ValueError("Invalid incident evidence")
            cell_id = h3.latlng_to_cell(latitude, longitude, resolution)
        except (KeyError, TypeError, AttributeError, ValueError, OverflowError):
            excluded_invalid += 1
            continue
        groups[cell_id].append({
            "severity": int(severity),
            "confidence": confidence,
            "occurred_at": occurred_at,
            "provenance": incident_provenance(incident),
        })

    features = []
    provenances = []
    for cell_id, rows in sorted(groups.items()):
        # H3 returns latitude/longitude; GeoJSON requires longitude/latitude.
        ring = [[longitude, latitude] for latitude, longitude in h3.cell_to_boundary(cell_id)]
        ring.append(ring[0][:])
        sources = [row["provenance"] for row in rows]
        provenances.extend(sources)
        features.append({
            "type": "Feature",
            "id": cell_id,
            "geometry": {"type": "Polygon", "coordinates": [ring]},
            "properties": {
                "cell_id": cell_id,
                "resolution": resolution,
                "incident_count": len(rows),
                "max_severity": max(row["severity"] for row in rows),
                "average_confidence": round(sum(row["confidence"] for row in rows) / len(rows), 4),
                "latest_occurred_at": max(row["occurred_at"] for row in rows).isoformat(),
                "provenance": combined_provenance(sources),
                "demo_incident_count": sources.count("demo"),
            },
        })
    return {
        "type": "FeatureCollection",
        "features": features,
        "metadata": {
            "resolution": resolution,
            "generated_at": current.isoformat(),
            "incident_count": sum(len(rows) for rows in groups.values()),
            "cell_count": len(features),
            "provenance": combined_provenance(provenances),
            "source": "active_incident_reports",
            "includes_expired": False,
            "excluded_invalid": excluded_invalid,
        },
    }
