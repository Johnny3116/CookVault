from fastapi import APIRouter, HTTPException, Response, status
from pydantic import BaseModel

from app.auth import COOKIE_NAME
from app.config import settings

router = APIRouter(prefix="/auth", tags=["auth"])


class LoginRequest(BaseModel):
    password: str


@router.get("/status")
def auth_status():
    return {"auth_required": bool(settings.cookvault_password)}


@router.post("/login")
def login(payload: LoginRequest, response: Response):
    if not settings.cookvault_password:
        return {"auth_required": False, "ok": True}
    if payload.password != settings.cookvault_password:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Incorrect password")
    response.set_cookie(
        COOKIE_NAME,
        settings.cookvault_password,
        httponly=True,
        samesite="lax",
        max_age=60 * 60 * 24 * 30,
    )
    return {"auth_required": True, "ok": True}
