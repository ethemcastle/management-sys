"""Application settings (pydantic-settings, env-overridable)."""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent


class Settings(BaseSettings):
    """Runtime configuration. Override any field via env or a .env file."""

    model_config = SettingsConfigDict(env_prefix="CADENCE_", env_file=".env", extra="ignore")

    # SQLite for dev; swap to e.g. postgresql+psycopg://user:pass@host/db for prod.
    database_url: str = f"sqlite:///{BASE_DIR / 'cadence.db'}"

    # CORS origins for the Angular dev server(s).
    cors_origins: list[str] = [
        "http://localhost:4200",
        "http://127.0.0.1:4200",
    ]

    # Seed the DB from seed_data.json on startup when the DB is empty.
    seed_on_startup: bool = True

    # Auto-generated, unique external Task ID prefix (e.g. RISR-0001).
    task_id_prefix: str = "RISR"

    # Artificial latency (seconds) for the mock AI endpoints so the UI's
    # loading states read naturally. Set to 0 in tests. Skipped automatically
    # when a real AI key is configured (the model supplies its own latency).
    ai_latency_seconds: float = 1.6

    # AI: when an API key is set, a real (free-tier) LLM generates summaries and
    # assistant answers via `LiveAiService`; otherwise the deterministic mock ships.
    # `ai_provider` selects the API shape: "gemini" (Google native) or "openai"
    # (any OpenAI-compatible chat endpoint — Groq, OpenRouter, Mistral, Ollama).
    ai_api_key: str | None = None
    ai_provider: str = "gemini"
    ai_model: str = "gemini-2.0-flash"
    ai_base_url: str = "https://generativelanguage.googleapis.com/v1beta"

    # Inbox: when a mailbox address + app password are set, the live IMAP mail
    # service imports real emails (`LiveMailService`); otherwise the seeded mock
    # inbox ships. Gmail: turn on 2-Step Verification, create an App Password at
    # myaccount.google.com/apppasswords, and set the two vars below.
    mail_address: str | None = None
    mail_app_password: str | None = None
    mail_imap_host: str = "imap.gmail.com"
    mail_sync_limit: int = 40  # how many recent INBOX messages to import

    # Recaps intake: optional shared secret for POST /api/recaps/webhook, so a
    # notetaker (Fireflies/Fathom) or the Gemini bridge can push recaps securely.
    recaps_webhook_secret: str | None = None
    # Recaps pull: a Google Apps Script web-app /exec URL that risr/crm GETs (with
    # the secret as ?token=) to fetch Gemini recaps — no inbound public URL needed.
    recaps_script_url: str | None = None

    # GitHub: when a token (fine-grained PAT or installation token) is set, the
    # live GitHub service is used instead of the mock; otherwise the mock ships.
    github_token: str | None = None
    github_api: str = "https://api.github.com"

    # Google Calendar: client id/secret drive the device-flow login; once a token
    # is obtained it goes in google_token and the live calendar service is used.
    google_client_id: str | None = None
    google_client_secret: str | None = None
    google_token: str | None = None
    google_refresh_token: str | None = None
    google_calendar_api: str = "https://www.googleapis.com/calendar/v3"
    google_token_uri: str = "https://oauth2.googleapis.com/token"

    # monday.com: when a personal API token is set, the live monday service imports
    # real boards/items via the GraphQL API (`LiveMondayService`); otherwise a
    # deterministic mock workspace ships. Create a token at monday.com → avatar →
    # Developers → My access tokens.
    monday_token: str | None = None
    monday_api: str = "https://api.monday.com/v2"

    # Zoom: when Server-to-Server OAuth creds are set, `LiveZoomService` pulls the
    # real AI Companion meeting summary; otherwise a realistic mock recap ships.
    # Create a Server-to-Server OAuth app at marketplace.zoom.us (scopes:
    # meeting:read:summary, meeting:read:list_summaries).
    zoom_account_id: str | None = None
    zoom_client_id: str | None = None
    zoom_client_secret: str | None = None
    zoom_api: str = "https://api.zoom.us/v2"
    zoom_oauth: str = "https://zoom.us/oauth/token"

    # Ybug: visual feedback → board tickets. Real-time via the webhook (Ybug POSTs
    # to /api/ybug/webhook; verify with the webhook secret), or poll the REST API
    # with an API key. Without either, a mock/simulate flow ships.
    ybug_api_key: str | None = None
    ybug_project_id: str | None = None
    ybug_webhook_secret: str | None = None
    ybug_api: str = "https://api.ybug.io"

    @property
    def seed_data_path(self) -> Path:
        return BASE_DIR / "seed_data.json"


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
