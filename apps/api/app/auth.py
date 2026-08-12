import hashlib
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Literal
from uuid import UUID, uuid4

import jwt
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pwdlib import PasswordHash
from sqlalchemy import select
from sqlalchemy.orm import Session

from .config import settings
from .database.models import RefreshSession, User
from .database.session import database_session

Role = Literal["driver", "fleet_manager", "administrator", "incident_moderator"]
password_hash = PasswordHash.recommended()
bearer = HTTPBearer(auto_error=False)


@dataclass(frozen=True)
class Principal:
    id: UUID
    email: str
    name: str
    role: Role


@dataclass
class MemoryUser:
    id: UUID
    email: str
    name: str
    password_hash: str
    role: Role
    is_active: bool = True


@dataclass
class MemoryRefreshSession:
    id: UUID
    user_id: UUID
    token_hash: str
    expires_at: datetime
    revoked_at: datetime | None = None


MEMORY_USERS: dict[UUID, MemoryUser] = {}
MEMORY_REFRESH_SESSIONS: dict[str, MemoryRefreshSession] = {}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _token_hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _principal(user: User | MemoryUser) -> Principal:
    return Principal(id=user.id, email=user.email, name=user.name, role=user.role)  # type: ignore[arg-type]


def find_user_by_email(email: str, db: Session | None) -> User | MemoryUser | None:
    normalized = email.casefold().strip()
    if settings.storage_backend == "mysql" and db:
        return db.scalar(select(User).where(User.email == normalized))
    return next((user for user in MEMORY_USERS.values() if user.email == normalized), None)


def find_user_by_id(user_id: UUID, db: Session | None) -> User | MemoryUser | None:
    if settings.storage_backend == "mysql" and db:
        return db.get(User, user_id)
    return MEMORY_USERS.get(user_id)


def register_user(email: str, name: str, password: str, role: Role, db: Session | None):
    normalized = email.casefold().strip()
    if find_user_by_email(normalized, db):
        raise HTTPException(409, "An account with this email already exists")
    encoded = password_hash.hash(password)
    if settings.storage_backend == "mysql" and db:
        user = User(email=normalized, name=name.strip(), password_hash=encoded, role=role)
        db.add(user)
        db.commit()
        db.refresh(user)
        return user
    user = MemoryUser(uuid4(), normalized, name.strip(), encoded, role)
    MEMORY_USERS[user.id] = user
    return user


def authenticate_user(email: str, password: str, db: Session | None):
    user = find_user_by_email(email, db)
    if not user or not user.is_active or not password_hash.verify(password, user.password_hash):
        raise HTTPException(401, "Email or password is incorrect", headers={"WWW-Authenticate": "Bearer"})
    return user


def create_access_token(user: User | MemoryUser) -> tuple[str, int]:
    now = _now()
    expires = now + timedelta(minutes=settings.jwt_expiry_minutes)
    token = jwt.encode(
        {
            "sub": str(user.id),
            "role": user.role,
            "iss": settings.jwt_issuer,
            "aud": settings.jwt_audience,
            "iat": now,
            "nbf": now,
            "exp": expires,
            "jti": str(uuid4()),
        },
        settings.jwt_secret,
        algorithm="HS256",
    )
    return token, int((expires - now).total_seconds())


def create_refresh_token(user: User | MemoryUser, db: Session | None) -> str:
    token = secrets.token_urlsafe(48)
    digest = _token_hash(token)
    expires = _now() + timedelta(days=settings.refresh_expiry_days)
    if settings.storage_backend == "mysql" and db:
        db.add(RefreshSession(user_id=user.id, token_hash=digest, expires_at=expires))
        db.commit()
    else:
        MEMORY_REFRESH_SESSIONS[digest] = MemoryRefreshSession(uuid4(), user.id, digest, expires)
    return token


def rotate_refresh_token(token: str, db: Session | None):
    digest = _token_hash(token)
    now = _now()
    if settings.storage_backend == "mysql" and db:
        session = db.scalar(select(RefreshSession).where(RefreshSession.token_hash == digest))
    else:
        session = MEMORY_REFRESH_SESSIONS.get(digest)
    if not session or session.revoked_at or session.expires_at <= now:
        raise HTTPException(401, "Refresh session is invalid or expired")
    session.revoked_at = now
    user = find_user_by_id(session.user_id, db)
    if not user or not user.is_active:
        raise HTTPException(401, "Account is unavailable")
    if settings.storage_backend == "mysql" and db:
        db.commit()
    access_token, expires_in = create_access_token(user)
    return access_token, create_refresh_token(user, db), expires_in


def revoke_refresh_token(token: str, db: Session | None) -> None:
    digest = _token_hash(token)
    if settings.storage_backend == "mysql" and db:
        session = db.scalar(select(RefreshSession).where(RefreshSession.token_hash == digest))
    else:
        session = MEMORY_REFRESH_SESSIONS.get(digest)
    if session and not session.revoked_at:
        session.revoked_at = _now()
        if settings.storage_backend == "mysql" and db:
            db.commit()


def decode_access_token(token: str) -> UUID:
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret,
            algorithms=["HS256"],
            audience=settings.jwt_audience,
            issuer=settings.jwt_issuer,
            options={"require": ["sub", "exp", "iat", "jti"]},
        )
        return UUID(payload["sub"])
    except (jwt.PyJWTError, ValueError, KeyError) as error:
        raise HTTPException(401, "Access token is invalid or expired", headers={"WWW-Authenticate": "Bearer"}) from error


def principal_from_credentials(credentials: HTTPAuthorizationCredentials | None, db: Session) -> Principal:
    if not credentials:
        raise HTTPException(401, "Authentication is required", headers={"WWW-Authenticate": "Bearer"})
    user = find_user_by_id(decode_access_token(credentials.credentials), db)
    if not user or not user.is_active:
        raise HTTPException(401, "Account is unavailable")
    return _principal(user)


def current_principal(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
    db: Session = Depends(database_session),
) -> Principal:
    return principal_from_credentials(credentials, db)


def require_when_enabled(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
    db: Session = Depends(database_session),
) -> Principal | None:
    return principal_from_credentials(credentials, db) if settings.require_auth else None


def require_roles_when_enabled(*roles: Role):
    def dependency(
        credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
        db: Session = Depends(database_session),
    ) -> Principal | None:
        if not settings.require_auth:
            return None
        principal = principal_from_credentials(credentials, db)
        if principal.role not in roles:
            raise HTTPException(403, "Your role does not permit this action")
        return principal
    return dependency


def require_roles(*roles: Role):
    def dependency(principal: Principal = Depends(current_principal)) -> Principal:
        if principal.role not in roles:
            raise HTTPException(403, "Your role does not permit this action")
        return principal
    return dependency
