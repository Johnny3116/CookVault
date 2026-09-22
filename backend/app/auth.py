"""Optional single-password gate.

This is a Tailscale-only, single-user app, so auth is opt-in rather than
mandatory (see spec section 7: "don't over-engineer auth/multi-tenancy").
When COOKVAULT_PASSWORD is unset, every check is a no-op.

When it is set, the session cookie holds an HMAC-signed token rather than the
password itself, so a leaked cookie doesn't hand over the password, and the
token ages out on its own.
"""

from __future__ import annotations

import hashlib
import hmac
import time

from fastapi import Cookie, HTTPException, status

from app.config import settings

COOKIE_NAME = "cookvault_session"
MAX_AGE_SECONDS = 60 * 60 * 24 * 30


def auth_enabled() -> bool:
    return bool(settings.cookvault_password)


def _sign(issued_at: int) -> str:
    assert settings.cookvault_password is not None
    return hmac.new(
        settings.cookvault_password.encode(),
        str(issued_at).encode(),
        hashlib.sha256,
    ).hexdigest()


def issue_token() -> str:
    issued_at = int(time.time())
    return f"{issued_at}.{_sign(issued_at)}"


def token_is_valid(token: str | None) -> bool:
    if not token:
        return False
    issued_at_raw, _, signature = token.partition(".")
    if not signature:
        return False
    try:
        issued_at = int(issued_at_raw)
    except ValueError:
        return False
    if not hmac.compare_digest(signature, _sign(issued_at)):
        return False
    return 0 <= time.time() - issued_at <= MAX_AGE_SECONDS


def require_auth(cookvault_session: str | None = Cookie(default=None, alias=COOKIE_NAME)) -> None:
    if not auth_enabled():
        return
    if not token_is_valid(cookvault_session):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
