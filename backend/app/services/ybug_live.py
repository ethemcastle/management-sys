"""Live Ybug REST poll. Activated when `CADENCE_YBUG_API_KEY` is set. Fetches
recent feedback for the configured project so a manual/interval Sync can create
tickets on localhost (where the webhook can't reach in). Best-effort: returns []
on any API error rather than inventing tickets. The real-time path is the webhook.

NOTE: the exact Ybug REST endpoint/shape is verified against the live API on
first connect; the paths below follow the public-beta docs and are guarded.
"""
from __future__ import annotations

import httpx

from app.config import settings
from app.services.ybug_service import MockYbugService


class YbugApiError(RuntimeError):
    def __init__(self, message: str, status: int | None = None):
        super().__init__(message)
        self.status = status


class LiveYbugService(MockYbugService):
    def account_name(self) -> str:
        try:
            data = self._get(f"/projects/{settings.ybug_project_id}")
            name = data.get("name") or data.get("domain")
            if name:
                return f"Ybug · {name}"
        except YbugApiError:
            pass
        return "Ybug"

    def fetch_new(self, since_id: str | None) -> list[dict]:
        try:
            data = self._get(
                f"/projects/{settings.ybug_project_id}/feedback", params={"limit": 50}
            )
        except YbugApiError:
            return []
        items = data if isinstance(data, list) else (data.get("data") or data.get("feedback") or [])
        return [f for f in items if not since_id or str(f.get("id", "")) > str(since_id)]

    def _get(self, path: str, params: dict | None = None) -> dict:
        try:
            resp = httpx.get(
                f"{settings.ybug_api}{path}",
                headers={
                    "Authorization": f"Bearer {settings.ybug_api_key}",
                    "Accept": "application/json",
                },
                params=params,
                timeout=20.0,
            )
        except httpx.HTTPError as exc:
            raise YbugApiError(str(exc)) from exc
        if resp.status_code >= 400:
            raise YbugApiError(f"Ybug API {resp.status_code}", resp.status_code)
        return resp.json()
