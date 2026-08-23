from fastapi import APIRouter, HTTPException

from ..repositories import repository
from ..risk.engine import risk_level, route_score, segment_score
from ..schemas import RouteAnalyseRequest
from .. import services

router = APIRouter(prefix="/api/v1/routes", tags=["routes"])

BASELINES = {
    "route-balanced": {"crime": 10, "accident": 7, "traffic": 11, "weather": 2, "road_condition": 4, "community": 3},
    "route-safest": {"crime": 5, "accident": 4, "traffic": 7, "weather": 2, "road_condition": 3, "community": 2},
    "route-fastest": {"crime": 18, "accident": 12, "traffic": 16, "weather": 3, "road_condition": 6, "community": 5},
}
DEFAULT_BASELINE = {"crime": 8, "accident": 6, "traffic": 8, "weather": 2, "road_condition": 4, "community": 3}
PREFERENCE_WEIGHTS = {"safest": (0.9, 0.1), "balanced": (0.75, 0.25), "fastest": (0.35, 0.65)}


@router.post("/analyse")
async def analyse(request: RouteAnalyseRequest):
    options = await services.route_provider.alternatives(request.origin, request.destination)
    incidents = services.active_risk_incidents()
    fastest = min(option["duration_minutes"] for option in options)

    for option in options:
        scores, totals, confidences = [], {}, []
        for latitude, longitude in option["geometry"]:
            score, penalties, confidence = segment_score(
                (latitude, longitude), incidents, BASELINES.get(option["id"], DEFAULT_BASELINE)
            )
            scores.append(score)
            confidences.append(confidence)
            for key, value in penalties.items():
                totals[key] = totals.get(key, 0) + value / len(option["geometry"])

        midpoint = option["geometry"][len(option["geometry"]) // 2]
        weather_penalty, weather_factors = await services.weather_provider.penalty(*midpoint)
        totals["weather"] = totals.get("weather", 0) + weather_penalty
        scores = [max(0, score - weather_penalty) for score in scores]
        confidence = round(sum(confidences) / len(confidences), 2)
        safety = route_score(scores, confidence)
        option.update(
            safety_score=safety,
            confidence=confidence,
            risk_level=risk_level(safety),
            difference_from_fastest=option["duration_minutes"] - fastest,
            breakdown={key: round(value, 1) for key, value in totals.items()},
            factors=(weather_factors + [key.replace("_", " ").title() for key, value in sorted(totals.items(), key=lambda item: item[1], reverse=True)])[:3],
            segment_scores=scores,
        )

    safety_weight, time_weight = PREFERENCE_WEIGHTS[request.preference]
    for option in options:
        efficiency = 100 * fastest / option["duration_minutes"]
        option["utility"] = round(safety_weight * option["safety_score"] + time_weight * efficiency, 2)
    recommended = max(options, key=lambda option: option["utility"])
    if request.preference == "balanced":
        recommended = next((option for option in options if option["id"] == "route-balanced"), recommended)

    for option in options:
        option["recommended"] = option is recommended
        option["explanation"] = (
            f"This route is {option['difference_from_fastest']} minutes slower than the fastest option and "
            f"balances {', '.join(option['factors'][:2]).lower()} exposure using recent, confidence-weighted reports."
        )
        option["geometry"] = [{"latitude": latitude, "longitude": longitude} for latitude, longitude in option["geometry"]]
        repository.save_route(option)
    return {
        "routes": options,
        "provider": getattr(services.route_provider, "last_source", "fallback"),
        "disclaimer": "Safety scores are decision-support estimates based on available data and do not guarantee safety.",
    }


@router.get("/{route_id}")
def get_route(route_id: str):
    route = repository.get_route(route_id)
    if not route:
        raise HTTPException(404, "Route not found; analyse routes first")
    return route
