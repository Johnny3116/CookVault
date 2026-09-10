from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg://cookvault:cookvault@postgres:5432/cookvault"

    # Optional single-password gate. Unset (default) means no auth at all --
    # reasonable for a Tailscale-only, single-user app.
    cookvault_password: str | None = None

    # Phase 2 -- not used yet. See app/agent_zero_client.py for what's pending
    # before this is wired up for real.
    agent_zero_base_url: str | None = None
    agent_zero_api_key: str | None = None

    cors_origins: list[str] = ["http://localhost:3420"]


settings = Settings()
