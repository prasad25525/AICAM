"""Hardcoded single-user login with HMAC-signed, expiring bearer tokens."""

import base64
import hashlib
import hmac
import json
import time

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.config import settings

bearer = HTTPBearer(auto_error=False)


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def _unb64(data: str) -> bytes:
    return base64.urlsafe_b64decode(data + "=" * (-len(data) % 4))


def _sign(payload: str) -> str:
    return _b64(hmac.new(settings.secret_key.encode(), payload.encode(), hashlib.sha256).digest())


def check_credentials(username: str, password: str) -> bool:
    user_ok = hmac.compare_digest(username.encode(), settings.admin_username.encode())
    pass_ok = hmac.compare_digest(password.encode(), settings.admin_password.encode())
    return user_ok and pass_ok


# "api" tokens go in the Authorization header. "media" tokens are short-lived and only accepted
# as ?token= on live-stream and event-image URLs, because <img src> cannot send headers.
API_SCOPE = "api"
MEDIA_SCOPE = "media"
MEDIA_PATH_SUFFIXES = ("/stream", "/image", "/frame")


def create_token(username: str, scope: str = API_SCOPE, minutes: int | None = None) -> tuple[str, int]:
    expires_at = int(time.time()) + (minutes or settings.token_expire_minutes) * 60
    payload = _b64(json.dumps({"sub": username, "exp": expires_at, "scope": scope}).encode())
    return f"{payload}.{_sign(payload)}", expires_at


def verify_token(token: str, scope: str = API_SCOPE) -> str | None:
    try:
        payload, signature = token.split(".")
        if not hmac.compare_digest(signature, _sign(payload)):
            return None
        data = json.loads(_unb64(payload))
    except ValueError:
        return None
    if data.get("exp", 0) < time.time() or data.get("scope", API_SCOPE) != scope:
        return None
    return data.get("sub")


def require_user(request: Request, creds: HTTPAuthorizationCredentials | None = Depends(bearer)) -> str:
    username = verify_token(creds.credentials) if creds else None
    if not username and request.url.path.endswith(MEDIA_PATH_SUFFIXES) and "token" in request.query_params:
        username = verify_token(request.query_params["token"], scope=MEDIA_SCOPE)
    if not username:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return username
