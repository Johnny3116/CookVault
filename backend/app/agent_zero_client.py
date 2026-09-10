"""Phase 2 stub -- intentionally not implemented yet.

CookVault's recipe-parsing and recipe-finder features are meant to call the
existing Agent Zero instance on NexusServer (`settings.agent_zero_base_url`,
key in `settings.agent_zero_api_key`). Public research confirms Agent Zero
exposes an `X-API-KEY`-authenticated REST API with endpoints like
`/api_message`, but the exact request/response JSON shape is NOT publicly
documented.

Before writing real code here:
1. Hit the live instance directly (or read its source under `python/api/` on
   whichever box runs it) to confirm the actual field names for sending a
   message and reading back the agent's reply.
2. Decide how to keep Agent Zero's replies scoped to "just answer with JSON"
   rather than letting it invoke its own browsing/code-execution tools, which
   are unnecessary and slower for a narrow text-structuring task.

Until then, these functions raise rather than guessing at a contract and
silently returning wrong data.
"""

from app.config import settings


class AgentZeroNotConfigured(RuntimeError):
    pass


def _ensure_configured() -> None:
    if not settings.agent_zero_base_url or not settings.agent_zero_api_key:
        raise AgentZeroNotConfigured("AGENT_ZERO_BASE_URL / AGENT_ZERO_API_KEY are not set")


def structure_recipe_text(raw_text: str, source_url: str | None = None) -> dict:
    """Turn raw recipe text (video transcript, description, or scraped page) into
    the four-column recipe structure + steps. Not implemented -- see module docstring.
    """
    _ensure_configured()
    raise NotImplementedError("Agent Zero integration not wired yet -- see module docstring")


def parse_finder_query(query: str) -> dict:
    """Turn a free-text finder query (budget/time/mood/ingredients) into structured
    search criteria. Not implemented -- see module docstring.
    """
    _ensure_configured()
    raise NotImplementedError("Agent Zero integration not wired yet -- see module docstring")
