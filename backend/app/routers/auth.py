import hmac

from fastapi import APIRouter, HTTPException, Response, status
from pydantic import BaseModel

from app.auth import COOKIE_NAME, MAX_AGE_SECONDS, auth_enabled, issue_token
from app.config import settings

router = APIRouter(prefix="/auth", tags=["auth"])


class LoginRequest(BaseModel):
    password: str


@router.get("/status")
def auth_status():
    return {"auth_required": auth_enabled()}


@router.post("/login")
def login(payload: LoginRequest, response: Response):
    if not auth_enabled():
        return {"auth_required": False, "ok": True}
    assert settings.cookvault_password is not None
    if not hmac.compare_digest(payload.password, settings.cookvault_password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Incorrect password")
    # The frontend proxies /api/* from its own origin, so this cookie is
    # same-origin and samesite=lax is both sufficient and actually sent.
    response.set_cookie(
        COOKIE_NAME,
        issue_token(),
        httponly=True,
        samesite="lax",
        max_age=MAX_AGE_SECONDS,
        path="/",
    )
    return {"auth_required": True, "ok": True}


@router.post("/logout")
def logout(response: Response):
    response.delete_cookie(COOKIE_NAME, path="/")
    return {"ok": True}
