from dataclasses import dataclass
from datetime import datetime, timezone
from math import exp, radians, sin, cos, asin, sqrt

WEIGHTS = {"crime": .35, "accident": .25, "traffic": .15, "weather": .10, "road_condition": .10, "community": .05}

@dataclass(frozen=True)
class RiskIncident:
    category: str
    severity: int
    confidence: float
    occurred_at: datetime
    latitude: float
    longitude: float
    relevance: float = 1.0

def haversine_km(a: tuple[float, float], b: tuple[float, float]) -> float:
    lat1, lon1, lat2, lon2 = map(radians, (*a, *b))
    dlat, dlon = lat2 - lat1, lon2 - lon1
    value = sin(dlat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(dlon / 2) ** 2
    return 6371 * 2 * asin(sqrt(value))

def recency_decay(occurred_at: datetime, now: datetime | None = None, half_life_hours: float = 6) -> float:
    now = now or datetime.now(timezone.utc)
    occurred_at = occurred_at if occurred_at.tzinfo else occurred_at.replace(tzinfo=timezone.utc)
    age = max(0, (now - occurred_at).total_seconds() / 3600)
    return 2 ** (-age / half_life_hours)

def distance_decay(distance_km: float, radius_km: float = 2.0) -> float:
    return exp(-max(0, distance_km) / radius_km)

def segment_score(point: tuple[float, float], incidents: list[RiskIncident], baseline: dict[str, float]) -> tuple[float, dict[str, float], float]:
    penalties = {key: max(0.0, baseline.get(key, 0.0)) * weight for key, weight in WEIGHTS.items()}
    evidence = []
    for incident in incidents:
        category = incident.category if incident.category in penalties else "community"
        proximity = distance_decay(haversine_km(point, (incident.latitude, incident.longitude)))
        impact = (incident.severity / 5) * incident.confidence * recency_decay(incident.occurred_at) * proximity * incident.relevance
        penalties[category] += impact * 100 * WEIGHTS[category]
        if proximity > .15: evidence.append(incident.confidence)
    penalties = {key: round(min(45, value), 2) for key, value in penalties.items()}
    score = max(0, min(100, 100 - sum(penalties.values())))
    confidence = sum(evidence) / len(evidence) if evidence else .72
    return round(score, 1), penalties, round(confidence, 2)

def route_score(segment_scores: list[float], confidence: float) -> float:
    if not segment_scores: return 0
    average, worst = sum(segment_scores) / len(segment_scores), min(segment_scores)
    confidence_adjusted = average * (.75 + .25 * confidence)
    return round(max(0, min(100, .50 * average + .30 * worst + .20 * confidence_adjusted)), 1)

def risk_level(score: float) -> str:
    return "low" if score >= 80 else "medium" if score >= 60 else "high" if score >= 40 else "critical"
