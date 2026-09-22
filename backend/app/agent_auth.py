"""The key that lets Agent Zero in, and nothing else.

This is a second, separate door from `app.auth`. John's password gate issues a
browser cookie; the agent presents an `X-API-Key` header. They do not overlap
in either direction, deliberately:

- A cookie does not open the agent surface, so a mistake in the web UI cannot
  reach tools the UI has no business calling.
- The agent key does not open John's surface, so a leaked key does not become a
  way to promote drafts, delete recipes or restore a backup. The agent's key
  buys it exactly the endpoints under `/agent`, which are the ones that can
  only propose.

**Off unless configured.** With `AGENT_API_KEY` unset the whole surface answers
503. A tool API that quietly comes up open because nobody set a variable is the
kind of default that is only noticed afterwards.
"""

from __future__ import annotations

import hmac

from fastapi import Header, HTTPException, status

from app.config import AGENT_KEY_MIN_LENGTH, settings

HEADER_NAME = "X-API-Key"

# Re-exported for readers who come here first. A key shorter than this is
# refused at startup by app.config, so a weak key is a boot-time complaint
# rather than a 503 nobody can explain.
MIN_KEY_LENGTH = AGENT_KEY_MIN_LENGTH


def agent_enabled() -> bool:
    return bool(settings.agent_api_key)


def require_agent(x_api_key: str | None = Header(default=None, alias=HEADER_NAME)) -> None:
    if not agent_enabled():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=(
                "The agent surface is switched off. Set AGENT_API_KEY to enable it."
            ),
        )
    assert settings.agent_api_key is not None
    if x_api_key is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Missing {HEADER_NAME}",
        )
    # Constant time: a comparison that returns early leaks the key one
    # character at a time to anything that can measure it.
    if not hmac.compare_digest(x_api_key, settings.agent_api_key):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid {HEADER_NAME}",
        )
