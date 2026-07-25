"""Live Zoom implementation: pulls the real AI Companion meeting summary via the
Zoom API and maps it onto `RecapContent`. Activated when Server-to-Server OAuth
creds are set (`CADENCE_ZOOM_ACCOUNT_ID`/`CLIENT_ID`/`CLIENT_SECRET`). Best-effort:
falls back to the mock recap if the meeting can't be matched or has no summary.

Meeting matching: a calendar event's join link (`meet_link`) is expected to be a
Zoom URL like `https://zoom.us/j/{meetingId}`; the numeric id is extracted and used
against `GET /meetings/{meetingId}/meeting_summary`.
"""
from __future__ import annotations

import base64
import re

import httpx

from app.config import settings
from app.models.calendar import CalendarEvent
from app.services.calendar_service import RecapContent
from app.services.zoom_service import MockZoomService


class ZoomApiError(RuntimeError):
    def __init__(self, message: str, status: int | None = None):
        super().__init__(message)
        self.status = status


class LiveZoomService(MockZoomService):
    """Real AI Companion recap; mock is inherited as the graceful fallback."""

    def account_name(self) -> str:
        try:
            data = self._api("/users/me")
            name = data.get("email") or data.get("first_name")
            if name:
                return f"Zoom · {name}"
        except ZoomApiError:
            pass
        return super().account_name()

    def meeting_summary(self, event: CalendarEvent) -> RecapContent:
        meeting_id = self._meeting_id(event)
        if not meeting_id:
            return super().meeting_summary(event)  # no Zoom meeting to look up
        try:
            data = self._api(f"/meetings/{meeting_id}/meeting_summary")
        except ZoomApiError:
            return super().meeting_summary(event)  # not ready / no access → mock

        overview = (data.get("summary_overview") or "").strip()
        next_steps = [s for s in (data.get("next_steps") or []) if s]
        decisions = [
            (d.get("summary") or d.get("label") or "").strip()
            for d in (data.get("summary_details") or [])
            if isinstance(d, dict)
        ]
        decisions = [d for d in decisions if d]
        if not overview and not next_steps and not decisions:
            return super().meeting_summary(event)  # empty summary → mock
        return RecapContent(
            summary=overview or f"Zoom AI Companion recap for “{event.title}”.",
            action_items=next_steps,
            decisions=decisions,
        )

    # --- helpers ------------------------------------------------------------
    def _meeting_id(self, event: CalendarEvent) -> str | None:
        m = re.search(r"/j/(\d+)", event.meet_link or "")
        return m.group(1) if m else None

    def _token(self) -> str:
        creds = base64.b64encode(
            f"{settings.zoom_client_id}:{settings.zoom_client_secret}".encode()
        ).decode()
        try:
            resp = httpx.post(
                settings.zoom_oauth,
                params={"grant_type": "account_credentials", "account_id": settings.zoom_account_id},
                headers={"Authorization": f"Basic {creds}"},
                timeout=20.0,
            )
        except httpx.HTTPError as exc:
            raise ZoomApiError(str(exc)) from exc
        if resp.status_code >= 400:
            raise ZoomApiError(f"Zoom OAuth {resp.status_code}", resp.status_code)
        return resp.json().get("access_token", "")

    def _api(self, path: str) -> dict:
        token = self._token()
        try:
            resp = httpx.get(
                f"{settings.zoom_api}{path}",
                headers={"Authorization": f"Bearer {token}"},
                timeout=20.0,
            )
        except httpx.HTTPError as exc:
            raise ZoomApiError(str(exc)) from exc
        if resp.status_code >= 400:
            raise ZoomApiError(f"Zoom API {resp.status_code}", resp.status_code)
        return resp.json()
