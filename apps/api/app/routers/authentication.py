from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy.orm import Session

from ..auth import (
    Principal,
    authenticate_user,
    create_access_token,
    create_refresh_token,
    current_principal,
    register_user,
    revoke_refresh_token,
    rotate_refresh_token,
)
from ..database.session import database_session
from ..config import settings
from ..schemas import LoginRequest, RefreshRequest, RegisterRequest
from ..rate_limit import limiter

router = APIRouter(prefix="/api/v1/auth", tags=["authentication"])

def _mobile(request: Request) -> bool:
    return request.headers.get("X-RoadSignal-Client") == "mobile"

def _set_refresh_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        settings.refresh_cookie_name,
        token,
        max_age=settings.refresh_expiry_days * 86400,
        path="/api/v1/auth",
        secure=settings.environment == "production",
        httponly=True,
        samesite="strict",
    )

def _refresh_token(request: Request, body: RefreshRequest) -> str:
    token = body.refresh_token if _mobile(request) else request.cookies.get(settings.refresh_cookie_name)
    if not token:
        raise HTTPException(status_code=401, detail="Refresh session is missing")
    return token


def token_response(request: Request, response: Response, user, db: Session):
    access_token, expires_in = create_access_token(user)
    refresh_token = create_refresh_token(user, db)
    _set_refresh_cookie(response, refresh_token)
    payload = {
        "access_token": access_token,
        "token_type": "bearer",
        "expires_in": expires_in,
        "user": {"id": str(user.id), "email": user.email, "name": user.name, "role": user.role},
    }
    if _mobile(request):
        payload["refresh_token"] = refresh_token
    return payload


@router.post("/register", status_code=status.HTTP_201_CREATED)
@limiter.limit("5/minute")
def register(request: Request, response: Response, body: RegisterRequest, db: Session = Depends(database_session)):
    return token_response(request, response, register_user(body.email, body.name, body.password, body.role, db), db)


@router.post("/login")
@limiter.limit("5/minute")
def login(request: Request, response: Response, body: LoginRequest, db: Session = Depends(database_session)):
    return token_response(request, response, authenticate_user(body.email, body.password, db), db)


@router.post("/refresh")
@limiter.limit("15/minute")
def refresh(request: Request, response: Response, body: RefreshRequest, db: Session = Depends(database_session)):
    access_token, refresh_token, expires_in = rotate_refresh_token(_refresh_token(request, body), db)
    _set_refresh_cookie(response, refresh_token)
    payload = {"access_token": access_token, "token_type": "bearer", "expires_in": expires_in}
    if _mobile(request):
        payload["refresh_token"] = refresh_token
    return payload


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(request: Request, body: RefreshRequest, db: Session = Depends(database_session)):
    revoke_refresh_token(_refresh_token(request, body), db)
    response = Response(status_code=status.HTTP_204_NO_CONTENT)
    response.delete_cookie(settings.refresh_cookie_name, path="/api/v1/auth", secure=settings.environment == "production", httponly=True, samesite="strict")
    return response


@router.get("/me")
def me(principal: Principal = Depends(current_principal)):
    return {"id": str(principal.id), "email": principal.email, "name": principal.name, "role": principal.role}
