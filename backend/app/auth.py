from fastapi import Cookie, HTTPException, status

from app.config import settings

COOKIE_NAME = "cookvault_session"


def require_auth(cookvault_session: str | None = Cookie(default=None, alias=COOKIE_NAME)) -> None:
    """No-op when COOKVAULT_PASSWORD is unset -- this is a Tailscale-only,
    single-user app, so auth is opt-in rather than mandatory (see spec section 7:
    "don't over-engineer auth/multi-tenancy")."""
    if not settings.cookvault_password:
        return
    if cookvault_session != settings.cookvault_password:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
