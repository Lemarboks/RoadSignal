"""Run inside the API as root, against the private local integration volume."""
import json
from pathlib import Path

from app.auth import find_user_by_email, password_hash, register_user
from app.config import settings
from app.database.session import session_factory

if settings.environment != "development":
    raise SystemExit("Showcase account provisioning is disabled outside development")

account = json.loads(Path("/run/roadsignal/accounts.json").read_text())["roadsignal"]
with session_factory()() as db:
    existing = find_user_by_email(account["email"], db)
    if existing:
        if existing.role != "administrator" or not password_hash.verify(account["password"], existing.password_hash):
            raise SystemExit("An existing account differs; refusing to change its password or permissions")
        print("RoadSignal local operator already configured.")
    else:
        register_user(account["email"], "Showcase operator", account["password"], "administrator", db)
        print("RoadSignal local operator created; password remains in the private integration volume.")
