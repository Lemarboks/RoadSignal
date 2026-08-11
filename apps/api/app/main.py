from datetime import datetime, timedelta, timezone
from uuid import uuid4
from fastapi import Depends, FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from .config import settings
from .schemas import IncidentCreate, RouteAnalyseRequest, TripLocation
from .providers.routes import MockCapeTownRouteProvider, OpenRouteProvider, ResilientRouteProvider
from .providers.weather import OpenMeteoWeatherProvider
from .risk.engine import RiskIncident, risk_level, route_score, segment_score
from .incidents.confidence import ConfidenceEvidence, calculate_confidence
from .store import INCIDENTS, ROUTES, TRIPS, AUDIT_LOG, EVENTS
from .database.session import database_ready
from .middleware import SecurityHeadersMiddleware
from .routers import authentication
from .auth import require_roles_when_enabled, require_when_enabled
from .rate_limit import limiter
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

app = FastAPI(title="SafeRoute AI API", version="0.1.0", description="Route-risk decision support. Scores are estimates, not guarantees of safety.")
app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(CORSMiddleware, allow_origins=settings.allowed_origins, allow_credentials=True, allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"], allow_headers=["Authorization", "Content-Type", "X-Request-ID"])
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

def serialise(value):
    if isinstance(value, datetime): return value.isoformat()
    if isinstance(value, dict): return {k: serialise(v) for k,v in value.items()}
    if isinstance(value, list): return [serialise(v) for v in value]
    return value

def publish(kind: str, payload: dict):
    event = {"id":str(uuid4()),"type":kind,"occurred_at":datetime.now(timezone.utc).isoformat(),"payload":serialise(payload)}
    EVENTS.append(event); AUDIT_LOG.append(event)

def risk_incidents():
    mapping = {"Robbery":"crime","Hijacking attempt":"crime","Accident":"accident","Flooding":"weather","Pothole":"road_condition","Broken traffic light":"traffic","Road closure":"traffic","Protest":"community"}
    return [RiskIncident(mapping.get(i["incident_type"],"community"),i["severity"],i["confidence"],i["occurred_at"],i["location"]["latitude"],i["location"]["longitude"]) for i in INCIDENTS if i["status"] == "active"]

@app.get("/api/v1/health")
def health(): return {"status":"healthy","service":"saferoute-api"}

@app.get("/api/v1/ready")
def ready():
    database = database_ready()
    ready_now = settings.storage_backend == "memory" or database
    return {"status": "ready" if ready_now else "degraded", "storage": settings.storage_backend, "database": database}

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
        ROUTES[option["id"]]=option
    return {"routes":options,"provider":getattr(provider,"last_source","fallback"),"disclaimer":"Safety scores are decision-support estimates based on available data and do not guarantee safety."}

@app.get("/api/v1/routes/{route_id}")
def get_route(route_id: str):
    if route_id not in ROUTES: raise HTTPException(404,"Route not found; analyse routes first")
    return ROUTES[route_id]

@app.post("/api/v1/routes/{route_id}/start")
def start_route(route_id: str, principal=Depends(require_when_enabled)):
    if route_id not in ROUTES: raise HTTPException(404,"Route not found; analyse routes first")
    trip={"id":str(uuid4()),"route_id":route_id,"status":"active","progress":0,"safety_score":ROUTES[route_id]["safety_score"],"alerts":[],"started_at":datetime.now(timezone.utc)}
    TRIPS[trip["id"]]=trip; publish("trip.started",trip); return serialise(trip)

@app.post("/api/v1/trips/{trip_id}/location")
def update_location(trip_id: str, location: TripLocation, principal=Depends(require_when_enabled)):
    trip=TRIPS.get(trip_id)
    if not trip: raise HTTPException(404,"Trip not found")
    trip["progress"]=min(100,trip["progress"]+5); publish("driver.location",{"trip_id":trip_id,"progress":trip["progress"]}); return serialise(trip)

@app.get("/api/v1/trips/{trip_id}")
def get_trip(trip_id: str):
    if trip_id not in TRIPS: raise HTTPException(404,"Trip not found")
    return serialise(TRIPS[trip_id])

@app.get("/api/v1/trips/{trip_id}/alerts")
def trip_alerts(trip_id: str): return {"items":TRIPS.get(trip_id,{}).get("alerts",[])}

@app.post("/api/v1/trips/{trip_id}/end")
def end_trip(trip_id: str, principal=Depends(require_when_enabled)):
    if trip_id not in TRIPS: raise HTTPException(404,"Trip not found")
    TRIPS[trip_id]["status"]="completed"; publish("trip.ended",TRIPS[trip_id]); return serialise(TRIPS[trip_id])

@app.get("/api/v1/incidents")
def incidents(): return {"items":serialise(INCIDENTS),"total":len(INCIDENTS)}

@app.get("/api/v1/incidents/nearby")
def nearby(latitude: float, longitude: float, radius_km: float=10): return incidents()

@app.post("/api/v1/incidents")
def create_incident(body: IncidentCreate, principal=Depends(require_when_enabled)):
    confidence, flags=calculate_confidence(ConfidenceEvidence(gps_distance_km=0 if not body.reporter_location else .2))
    incident={"id":str(uuid4()),"incident_type":body.incident_type,"severity":body.severity,"source_type":"anonymous" if body.anonymous else "community","verification_status":"unverified","confidence":confidence,"description":body.description,"occurred_at":body.occurred_at,"expires_at":body.occurred_at+timedelta(hours=6),"location":body.location.model_dump(),"confirmations":0,"disputes":0,"status":"active","abuse_flags":flags}
    INCIDENTS.insert(0,incident); publish("incident.created",incident)
    for trip in TRIPS.values():
        if trip["status"]=="active" and body.severity>=4:
            trip["safety_score"]=max(20,round(trip["safety_score"]-18.5,1)); trip["alerts"].append("High-severity incident detected ahead. A safer alternative is available."); publish("route.risk_changed",{"trip_id":trip["id"],"safety_score":trip["safety_score"],"reroute":"route-safest"})
    return serialise(incident)

def moderate(incident_id: str, action: str):
    incident=next((x for x in INCIDENTS if x["id"]==incident_id),None)
    if not incident: raise HTTPException(404,"Incident not found")
    if action=="confirm": incident["confirmations"]+=1
    elif action=="dispute": incident["disputes"]+=1
    else: incident.update(status="resolved",verification_status="resolved")
    if action != "resolve": incident["confidence"],_=calculate_confidence(ConfidenceEvidence(confirmations=incident["confirmations"],disputes=incident["disputes"],reporter_trust=.5,account_age_days=180,previous_accuracy=.7))
    publish(f"incident.{action}",incident); return serialise(incident)

@app.post("/api/v1/incidents/{incident_id}/confirm")
def confirm(incident_id: str, principal=Depends(require_when_enabled)): return moderate(incident_id,"confirm")
@app.post("/api/v1/incidents/{incident_id}/dispute")
def dispute(incident_id: str, principal=Depends(require_when_enabled)): return moderate(incident_id,"dispute")
@app.post("/api/v1/incidents/{incident_id}/resolve")
def resolve(incident_id: str, principal=Depends(require_roles_when_enabled("administrator","incident_moderator"))): return moderate(incident_id,"resolve")

@app.get("/api/v1/fleets/demo-fleet/drivers")
def drivers(principal=Depends(require_roles_when_enabled("administrator","fleet_manager"))): return {"items":[{"id":f"driver-{i}","name":name,"status":"en_route" if i<3 else "available","safety_score":88-i*2} for i,name in enumerate(["Ayanda Ndlovu","Liam Jacobs","Thandi Mokoena","Ethan Williams","Naledi Dlamini","Luke Daniels","Zanele Khumalo","Mia Smith","Sibusiso Nkosi","Noah Adams"])]}
@app.get("/api/v1/fleets/demo-fleet/trips")
def fleet_trips(principal=Depends(require_roles_when_enabled("administrator","fleet_manager"))): return {"items":serialise(list(TRIPS.values())),"completed_today":20}
@app.get("/api/v1/fleets/demo-fleet/incidents")
def fleet_incidents(principal=Depends(require_roles_when_enabled("administrator","fleet_manager","incident_moderator"))): return incidents()
@app.get("/api/v1/fleets/demo-fleet/analytics")
def analytics(principal=Depends(require_roles_when_enabled("administrator","fleet_manager"))): return {"active_drivers":3,"high_risk_drivers":sum(1 for t in TRIPS.values() if t["safety_score"]<60),"average_safety_score":84.2,"active_incidents":sum(1 for i in INCIDENTS if i["status"]=="active"),"trips_completed_today":20,"alerts":EVENTS[-10:],"risk_by_area":[{"area":"Cape Town CBD","score":82},{"area":"Woodstock","score":71},{"area":"Pinelands","score":88},{"area":"Athlone","score":64}],"hourly_scores":[78,81,84,86,83,79,74,69]}

@app.get("/api/v1/audit-logs")
def audit_logs(principal=Depends(require_roles_when_enabled("administrator","incident_moderator"))): return {"items":AUDIT_LOG[-100:]}

@app.post("/api/v1/emergencies")
def emergency(payload: dict, principal=Depends(require_when_enabled)):
    event={"id":str(uuid4()),"status":"active","created_at":datetime.now(timezone.utc),"location":payload.get("location")}; publish("emergency.created",event); return serialise(event)
@app.post("/api/v1/emergencies/{event_id}/cancel")
def cancel_emergency(event_id: str, principal=Depends(require_when_enabled)): publish("emergency.cancelled",{"id":event_id}); return {"id":event_id,"status":"cancelled"}
@app.post("/api/v1/emergencies/{event_id}/resolve")
def resolve_emergency(event_id: str, principal=Depends(require_roles_when_enabled("administrator","fleet_manager"))): publish("emergency.resolved",{"id":event_id}); return {"id":event_id,"status":"resolved"}

@app.websocket("/api/v1/ws/events")
async def websocket_events(socket: WebSocket):
    await socket.accept(); cursor=len(EVENTS)
    try:
        while True:
            await socket.receive_text()
            for event in EVENTS[cursor:]: await socket.send_json(event)
            cursor=len(EVENTS)
    except WebSocketDisconnect: pass
