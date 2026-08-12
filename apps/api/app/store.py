from datetime import datetime, timedelta, timezone
from uuid import uuid4

NOW = datetime.now(timezone.utc)
INCIDENTS = [
 {"id":str(uuid4()),"incident_type":"Accident","severity":4,"source_type":"traffic","verification_status":"confirmed","confidence":.86,"description":"Two-vehicle collision near Hospital Bend","occurred_at":NOW-timedelta(minutes=35),"expires_at":NOW+timedelta(hours=2),"location":{"latitude":-33.941,"longitude":18.452},"confirmations":4,"disputes":0,"status":"active"},
 {"id":str(uuid4()),"incident_type":"Robbery","severity":4,"source_type":"community","verification_status":"verified","confidence":.72,"description":"Recent vehicle-crime report near Vanguard Drive","occurred_at":NOW-timedelta(hours=2),"expires_at":NOW+timedelta(hours=5),"location":{"latitude":-33.963,"longitude":18.478},"confirmations":3,"disputes":1,"status":"active"},
 {"id":str(uuid4()),"incident_type":"Broken traffic light","severity":2,"source_type":"municipal","verification_status":"confirmed","confidence":.9,"description":"Signal outage causing delays","occurred_at":NOW-timedelta(hours=1),"expires_at":NOW+timedelta(hours=8),"location":{"latitude":-33.951,"longitude":18.473},"confirmations":6,"disputes":0,"status":"active"},
]
ROUTES: dict[str, dict] = {}
TRIPS: dict[str, dict] = {}
TRIP_LOCATIONS: dict[str, list[dict]] = {}
AUDIT_LOG: list[dict] = []
EVENTS: list[dict] = []
