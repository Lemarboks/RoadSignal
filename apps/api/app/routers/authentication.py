from fastapi import APIRouter, Depends, Request, Response, status
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
from ..schemas import LoginRequest, RefreshRequest, RegisterRequest
from ..rate_limit import limiter

router = APIRouter(prefix="/api/v1/auth", tags=["authentication"])


def token_response(user, db: Session):
    access_token, expires_in = create_access_token(user)
    return {
        "access_token": access_token,
        "refresh_token": create_refresh_token(user, db),
        "token_type": "bearer",
        "expires_in": expires_in,
        "user": {"id": str(user.id), "email": user.email, "name": user.name, "role": user.role},
    }


@router.post("/register", status_code=status.HTTP_201_CREATED)
@limiter.limit("5/minute")
def register(request: Request, response: Response, body: RegisterRequest, db: Session = Depends(database_session)):
    return token_response(register_user(body.email, body.name, body.password, body.role, db), db)


@router.post("/login")
@limiter.limit("5/minute")
def login(request: Request, response: Response, body: LoginRequest, db: Session = Depends(database_session)):
    return token_response(authenticate_user(body.email, body.password, db), db)


@router.post("/refresh")
@limiter.limit("15/minute")
def refresh(request: Request, response: Response, body: RefreshRequest, db: Session = Depends(database_session)):
    access_token, refresh_token, expires_in = rotate_refresh_token(body.refresh_token, db)
    return {"access_token": access_token, "refresh_token": refresh_token, "token_type": "bearer", "expires_in": expires_in}


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(body: RefreshRequest, db: Session = Depends(database_session)):
    revoke_refresh_token(body.refresh_token, db)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/me")
def me(principal: Principal = Depends(current_principal)):
    return {"id": str(principal.id), "email": principal.email, "name": principal.name, "role": principal.role}
