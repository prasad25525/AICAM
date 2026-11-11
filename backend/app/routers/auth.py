from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.auth import MEDIA_SCOPE, check_credentials, create_token, require_user
from app.config import settings
from app.db import get_db
from app.routers.industries import switch_industry

router = APIRouter(prefix="/auth", tags=["auth"])


class LoginRequest(BaseModel):
    username: str
    password: str
    industry: str | None = None  # chosen on the login page; None keeps the current one


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_at: int


@router.post("/login", response_model=TokenResponse)
def login(body: LoginRequest, db: Session = Depends(get_db)):
    if not check_credentials(body.username, body.password):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid username or password")
    if body.industry:
        switch_industry(db, body.industry)  # only after the password check
    token, expires_at = create_token(body.username)
    return TokenResponse(access_token=token, expires_at=expires_at)


@router.get("/me")
def me(username: str = Depends(require_user)):
    return {"username": username}


@router.post("/media-token", response_model=TokenResponse)
def media_token(username: str = Depends(require_user)):
    """Short-lived token for <img src> URLs (?token=...): live streams and event images.
    A stream checks it only when it connects."""
    token, expires_at = create_token(username, scope=MEDIA_SCOPE, minutes=settings.media_token_minutes)
    return TokenResponse(access_token=token, expires_at=expires_at)
