import hmac

from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel

from app.auth import COOKIE_NAME, MAX_AGE_SECONDS, auth_enabled, issue_token, require_auth
from app.config import settings

router = APIRouter(prefix="/auth", tags=["auth"])


@router.get("/session", dependencies=[Depends(require_auth)])
def session_check():
    """Is this cookie good? 200 or 401, nothing else.

    Exists for the frontend's assistant proxy, which has to decide whether to
    forward a chat to the assistant service without knowing the signing key.
    It asks the one thing that does. With the gate off this is always 200,
    which is the same answer every other endpoint gives.
    """
    return {"authenticated": True}


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
