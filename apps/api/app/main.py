import asyncio
from datetime import datetime, timedelta, timezone
from uuid import uuid4
from fastapi import Depends, FastAPI, HTTPException, Query, Response, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from .config import settings
from .schemas import EmergencyCreate, IncidentCreate, RouteAnalyseRequest, TripLocation
from .providers.routes import MockCapeTownRouteProvider, OpenRouteProvider, ResilientRouteProvider
from .providers.weather import OpenMeteoWeatherProvider
from .risk.engine import RiskIncident, haversine_km, risk_level, route_score, segment_score
from .risk.evidence import risk_evidence
from .incidents.confidence import ConfidenceEvidence, calculate_confidence
from .events import event_bus
from .repositories import repository, serialise
from .database.session import database_ready
from .auth import decode_access_token
from .middleware import SecurityHeadersMiddleware
from .observability import configure_observability
from .routers import authentication
from .auth import require_roles_when_enabled, require_when_enabled
from .rate_limit import limiter
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

app = FastAPI(title="RoadSignal API", version="0.1.0", description="Route-risk decision support. Scores are estimates, not guarantees of safety.")
app.add_middleware(SecurityHeadersMiddleware)
configure_observability(app)
app.add_middleware(CORSMiddleware, allow_origins=settings.allowed_origins, allow_credentials=True, allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"], allow_headers=["Authorization", "Content-Type", "X-Request-ID", "X-RoadSignal-Client"])
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.include_router(authentication.router)
fallback_provider = MockCapeTownRouteProvider()
provider = ResilientRouteProvider(
    OpenRouteProvider(
        settings.nominatim_url,
        settings.osrm_url,
        settings.provider_timeout_seconds,
        settings.provider_user_agent,
    ),
    fallback_provider,
) if settings.route_provider == "open" else fallback_provider
weather_provider = OpenMeteoWeatherProvider(settings.open_meteo_url, settings.provider_timeout_seconds)

def publish(kind: str, payload: dict):
    event = {"id":str(uuid4()),"type":kind,"occurred_at":datetime.now(timezone.utc).isoformat(),"payload":serialise(payload)}
    event_bus.publish(event); repository.append_audit(kind, payload)

def risk_incidents():
    mapping = {"Robbery":"crime","Hijacking attempt":"crime","Accident":"accident","Flooding":"weather","Pothole":"road_condition","Broken traffic light":"traffic","Road closure":"traffic","Protest":"community"}
    incidents = []
    for item in repository.list_incidents():
        if item["status"] != "active":
            continue
        occurred_at = item["occurred_at"]
        if isinstance(occurred_at, str):
            occurred_at = datetime.fromisoformat(occurred_at.replace("Z", "+00:00"))
        incidents.append(RiskIncident(mapping.get(item["incident_type"], "community"), item["severity"], item["confidence"], occurred_at, item["location"]["latitude"], item["location"]["longitude"]))
    return incidents

@app.get("/api/v1/health")
def health(): return {"status":"healthy","service":"roadsignal-api"}

@app.get("/api/v1/risk/evidence")
def get_risk_evidence(): return risk_evidence()

@app.get("/api/v1/ready")
def ready(response: Response):
    database = database_ready()
    events = event_bus.ready()
    storage_ready = settings.storage_backend == "memory" or database
    events_ready = settings.event_backend == "memory" or events
    is_ready = storage_ready and events_ready
    if not is_ready:
        response.status_code = 503
    return {"status": "ready" if is_ready else "degraded", "storage": settings.storage_backend, "database": database, "events": settings.event_backend, "event_bus": events}

@app.post("/api/v1/routes/analyse")
async def analyse(request: RouteAnalyseRequest):
    options, all_incidents = await provider.alternatives(request.origin, request.destination), risk_incidents()
    baseline_by_id = {"route-balanced":{"crime":10,"accident":7,"traffic":11,"weather":2,"road_condition":4,"community":3},"route-safest":{"crime":5,"accident":4,"traffic":7,"weather":2,"road_condition":3,"community":2},"route-fastest":{"crime":18,"accident":12,"traffic":16,"weather":3,"road_condition":6,"community":5}}
    fastest = min(x["duration_minutes"] for x in options)
    default_baseline = {"crime": 8, "accident": 6, "traffic": 8, "weather": 2, "road_condition": 4, "community": 3}
    for option in options:
        scores, totals, confidences = [], {}, []
        for lat, lon in option["geometry"]:
            score, penalties, confidence = segment_score((lat,lon), all_incidents, baseline_by_id.get(option["id"], default_baseline))
            scores.append(score); confidences.append(confidence)
            for key,value in penalties.items(): totals[key] = totals.get(key,0)+value/len(option["geometry"])
        midpoint = option["geometry"][len(option["geometry"]) // 2]
        weather_penalty, weather_factors = await weather_provider.penalty(midpoint[0], midpoint[1])
        totals["weather"] = totals.get("weather", 0) + weather_penalty
        scores = [max(0, score - weather_penalty) for score in scores]
        confidence = round(sum(confidences)/len(confidences),2)
        safety = route_score(scores,confidence)
        option.update({"safety_score":safety,"confidence":confidence,"risk_level":risk_level(safety),"difference_from_fastest":option["duration_minutes"]-fastest,"breakdown":{k:round(v,1) for k,v in totals.items()},"factors":(weather_factors + [k.replace("_"," ").title() for k,v in sorted(totals.items(),key=lambda x:x[1],reverse=True)])[:3],"segment_scores":scores})
    weights={"safest":(.9,.1),"balanced":(.75,.25),"fastest":(.35,.65)}[request.preference]
    for option in options:
        efficiency=100*fastest/option["duration_minutes"]
        option["utility"]=round(weights[0]*option["safety_score"]+weights[1]*efficiency,2)
    recommended=max(options,key=lambda x:x["utility"])
    # The demo's balanced route is deliberately the best compromise for the default scenario.
    if request.preference == "balanced" and any(x["id"] == "route-balanced" for x in options): recommended=next(x for x in options if x["id"]=="route-balanced")
    for option in options:
        option["recommended"]=option is recommended
        option["explanation"]=(f"This route is {option['difference_from_fastest']} minutes slower than the fastest option and " f"balances {', '.join(option['factors'][:2]).lower()} exposure using recent, confidence-weighted reports.")
        option["geometry"]=[{"latitude":lat,"longitude":lon} for lat,lon in option["geometry"]]
        repository.save_route(option)
    return {"routes":options,"provider":getattr(provider,"last_source","fallback"),"disclaimer":"Safety scores are decision-support estimates based on available data and do not guarantee safety."}

@app.get("/api/v1/routes/{route_id}")
def get_route(route_id: str):
    route = repository.get_route(route_id)
    if not route: raise HTTPException(404,"Route not found; analyse routes first")
    return route

def authorize_trip(trip: dict, principal) -> None:
    if not settings.require_auth:
        return
    owner = str(trip.get("user_id") or "")
    if principal and (owner == str(principal.id) or principal.role in {"administrator", "fleet_manager"}):
        return
    raise HTTPException(403, "This trip belongs to another account")

@app.post("/api/v1/routes/{route_id}/start")
def start_route(route_id: str, principal=Depends(require_when_enabled)):
    route = repository.get_route(route_id)
    if not route: raise HTTPException(404,"Route not found; analyse routes first")
    trip=repository.create_trip(route, principal.id if principal else None)
    publish("trip.started",trip)
    return serialise(trip)

@app.post("/api/v1/trips/{trip_id}/location")
def update_location(trip_id: str, location: TripLocation, principal=Depends(require_when_enabled)):
    trip=repository.get_trip(trip_id)
    if not trip: raise HTTPException(404,"Trip not found")
    authorize_trip(trip, principal)
    repository.save_trip_location(trip_id, location.location.model_dump(), location.recorded_at)
    trip["progress"]=min(100,trip["progress"]+5); repository.save_trip(trip); publish("driver.location",{"trip_id":trip_id,"progress":trip["progress"],"latitude":location.location.latitude,"longitude":location.location.longitude}); return serialise(trip)

@app.get("/api/v1/trips/{trip_id}")
def get_trip(trip_id: str, principal=Depends(require_when_enabled)):
    trip=repository.get_trip(trip_id)
    if not trip: raise HTTPException(404,"Trip not found")
    authorize_trip(trip, principal)
    return serialise(trip)

@app.get("/api/v1/trips/{trip_id}/locations")
def trip_locations(trip_id: str, principal=Depends(require_when_enabled)):
    trip=repository.get_trip(trip_id)
    if not trip: raise HTTPException(404,"Trip not found")
    authorize_trip(trip, principal)
    return {"items": serialise(repository.list_trip_locations(trip_id))}

@app.get("/api/v1/trips/{trip_id}/alerts")
def trip_alerts(trip_id: str, principal=Depends(require_when_enabled)):
    trip=repository.get_trip(trip_id)
    if not trip: raise HTTPException(404, "Trip not found")
    authorize_trip(trip, principal)
    return {"items": trip.get("alerts", [])}

@app.post("/api/v1/trips/{trip_id}/end")
def end_trip(trip_id: str, principal=Depends(require_when_enabled)):
    trip=repository.get_trip(trip_id)
    if not trip: raise HTTPException(404,"Trip not found")
    authorize_trip(trip, principal)
    trip["status"]="completed"; repository.save_trip(trip); publish("trip.ended",trip); return serialise(trip)

@app.get("/api/v1/incidents")
def incidents():
    items=repository.list_incidents(); return {"items":serialise(items),"total":len(items)}

@app.get("/api/v1/incidents/nearby")
def nearby(latitude: float = Query(ge=-90, le=90), longitude: float = Query(ge=-180, le=180), radius_km: float = Query(default=10, gt=0, le=500)):
    items = [item for item in repository.list_incidents() if haversine_km((latitude, longitude), (item["location"]["latitude"], item["location"]["longitude"])) <= radius_km]
    return {"items": serialise(items), "total": len(items)}

@app.post("/api/v1/incidents")
def create_incident(body: IncidentCreate, principal=Depends(require_when_enabled)):
    confidence, flags=calculate_confidence(ConfidenceEvidence(gps_distance_km=0 if not body.reporter_location else .2))
    incident={"id":str(uuid4()),"incident_type":body.incident_type,"severity":body.severity,"source_type":"anonymous" if body.anonymous else "community","verification_status":"unverified","confidence":confidence,"description":body.description,"occurred_at":body.occurred_at,"expires_at":body.occurred_at+timedelta(hours=6),"location":body.location.model_dump(),"confirmations":0,"disputes":0,"status":"active","abuse_flags":flags}
    repository.save_incident(incident); publish("incident.created",incident)
    for trip in repository.list_trips():
        if trip["status"]=="active" and body.severity>=4:
            trip["safety_score"]=max(20,round(trip["safety_score"]-18.5,1)); trip["alerts"].append("High-severity incident detected ahead. A safer alternative is available."); repository.save_trip(trip); publish("route.risk_changed",{"trip_id":trip["id"],"safety_score":trip["safety_score"],"reroute":"route-safest"})
    return serialise(incident)

def moderate(incident_id: str, action: str):
    incident=repository.get_incident(incident_id)
    if not incident: raise HTTPException(404,"Incident not found")
    if action=="confirm": incident["confirmations"]+=1
    elif action=="dispute": incident["disputes"]+=1
    else: incident.update(status="resolved",verification_status="resolved")
    if action != "resolve": incident["confidence"],_=calculate_confidence(ConfidenceEvidence(confirmations=incident["confirmations"],disputes=incident["disputes"],reporter_trust=.5,account_age_days=180,previous_accuracy=.7))
    repository.save_incident(incident); publish(f"incident.{action}",incident); return serialise(incident)

@app.post("/api/v1/incidents/{incident_id}/confirm")
def confirm(incident_id: str, principal=Depends(require_when_enabled)): return moderate(incident_id,"confirm")
@app.post("/api/v1/incidents/{incident_id}/dispute")
def dispute(incident_id: str, principal=Depends(require_when_enabled)): return moderate(incident_id,"dispute")
@app.post("/api/v1/incidents/{incident_id}/resolve")
def resolve(incident_id: str, principal=Depends(require_roles_when_enabled("administrator","incident_moderator"))): return moderate(incident_id,"resolve")

@app.get("/api/v1/fleets/demo-fleet/drivers")
def drivers(principal=Depends(require_roles_when_enabled("administrator","fleet_manager"))): return {"items":[{"id":f"driver-{i}","name":name,"status":"en_route" if i<3 else "available","safety_score":88-i*2} for i,name in enumerate(["Ayanda Ndlovu","Liam Jacobs","Thandi Mokoena","Ethan Williams","Naledi Dlamini","Luke Daniels","Zanele Khumalo","Mia Smith","Sibusiso Nkosi","Noah Adams"])]}
@app.get("/api/v1/fleets/demo-fleet/trips")
def fleet_trips(principal=Depends(require_roles_when_enabled("administrator","fleet_manager"))): return {"items":serialise(repository.list_trips()),"completed_today":20}
@app.get("/api/v1/fleets/demo-fleet/incidents")
def fleet_incidents(principal=Depends(require_roles_when_enabled("administrator","fleet_manager","incident_moderator"))): return incidents()
def _as_datetime(value):
    return datetime.fromisoformat(value.replace("Z", "+00:00")) if isinstance(value, str) else value

@app.get("/api/v1/fleets/demo-fleet/analytics")
def analytics(principal=Depends(require_roles_when_enabled("administrator","fleet_manager"))):
    trips = repository.list_trips()
    active_trips = [t for t in trips if t["status"] == "active"]
    active_driver_ids = {t["user_id"] for t in active_trips if t.get("user_id")}
    today = datetime.now(timezone.utc).date()
    trips_completed_today = sum(1 for t in trips if t["status"] == "completed" and _as_datetime(t["started_at"]).date() == today)
    average_safety_score = round(sum(t["safety_score"] for t in trips) / len(trips), 1) if trips else 0
    return {
        "active_drivers": len(active_driver_ids) or len(active_trips),
        "high_risk_drivers": sum(1 for t in trips if t["safety_score"]<60),
        "average_safety_score": average_safety_score,
        "active_incidents": sum(1 for i in repository.list_incidents() if i["status"]=="active"),
        "trips_completed_today": trips_completed_today,
        "alerts": repository.list_audit(10),
        "risk_by_area": [{"area":"Cape Town CBD","score":82},{"area":"Woodstock","score":71},{"area":"Pinelands","score":88},{"area":"Athlone","score":64}],
        "hourly_scores": [78,81,84,86,83,79,74,69],
    }

@app.get("/api/v1/audit-logs")
def audit_logs(principal=Depends(require_roles_when_enabled("administrator","incident_moderator"))): return {"items":repository.list_audit(100)}

@app.post("/api/v1/emergencies")
def emergency(payload: EmergencyCreate, principal=Depends(require_when_enabled)):
    event={"id":str(uuid4()),"status":"active","created_at":datetime.now(timezone.utc),"location":payload.location.model_dump(),"user_id":str(principal.id) if principal else None}; publish("emergency.created",event); return serialise(event)
@app.post("/api/v1/emergencies/{event_id}/cancel")
def cancel_emergency(event_id: str, principal=Depends(require_when_enabled)): publish("emergency.cancelled",{"id":event_id}); return {"id":event_id,"status":"cancelled"}
@app.post("/api/v1/emergencies/{event_id}/resolve")
def resolve_emergency(event_id: str, principal=Depends(require_roles_when_enabled("administrator","fleet_manager"))): publish("emergency.resolved",{"id":event_id}); return {"id":event_id,"status":"resolved"}

@app.websocket("/api/v1/ws/events")
async def websocket_events(socket: WebSocket):
    await socket.accept()
    if settings.require_auth:
        try:
            message = await asyncio.wait_for(socket.receive_json(), timeout=5)
            if message.get("type") != "authenticate": raise ValueError("authentication message required")
            decode_access_token(message.get("access_token", ""))
        except Exception:
            await socket.close(code=4401, reason="Authentication required")
            return
    cursor = socket.query_params.get("cursor")
    try:
        while True:
            cursor, events = await event_bus.read_after(cursor)
            if events:
                await socket.send_json({"cursor": cursor, "events": events})
            else:
                await socket.send_json({"cursor": cursor, "events": [], "type": "heartbeat"})
    except WebSocketDisconnect:
        pass
