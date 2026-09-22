from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Long enough that guessing the agent key is not a strategy. It lives here
# rather than in app/agent_auth.py because the validator below runs while this
# module is still being imported, and reaching back into a half-built module is
# how a circular import starts.
AGENT_KEY_MIN_LENGTH = 32


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg://cookvault:cookvault@postgres:5432/cookvault"

    # Optional single-password gate. Unset (default) means no auth at all --
    # reasonable for a Tailscale-only, single-user app.
    cookvault_password: str | None = None

    # The key Agent Zero presents to reach the /agent tool surface. Unset
    # (default) means that surface is switched off entirely -- see
    # app/agent_auth.py. This is not the same credential as the password above
    # and does not open the same doors.
    agent_api_key: str | None = None

    # Phase 2, outbound half -- still not used. CookVault talking *to* Agent
    # Zero needs a wire contract nobody has verified yet; see
    # app/agent_zero_client.py. The tool surface above is the inbound half and
    # needs none of it, because there CookVault is the server.
    agent_zero_base_url: str | None = None
    agent_zero_api_key: str | None = None

    # Normally empty: the frontend proxies /api/* to the backend from its own
    # origin, so browser requests are same-origin and CORS never applies. Only
    # needed if you point a browser straight at the backend's port.
    cors_origins: list[str] = []

    @field_validator("agent_api_key")
    @classmethod
    def _agent_key_is_long_enough(cls, value: str | None) -> str | None:
        """Refuse to boot on a weak agent key.

        Failing here is deliberate. The alternative -- accepting it and
        answering 503 at request time -- turns a configuration mistake into a
        mystery, and this key is the only thing standing between the tool
        surface and anything that can reach the port.
        """
        if value is not None and len(value) < AGENT_KEY_MIN_LENGTH:
            raise ValueError(
                f"AGENT_API_KEY must be at least {AGENT_KEY_MIN_LENGTH} characters. "
                "Generate one with: python -c 'import secrets; print(secrets.token_urlsafe(32))'"
            )
        return value


settings = Settings()
