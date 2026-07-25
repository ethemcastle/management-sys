"""Live Google Calendar implementation of `CalendarService`.

Imports the current week's real events from the Google Calendar API and stores
them as `CalendarEvent` rows (the same shape the mock uses). Meeting *recaps*
stay on the mock (deterministic) — real recaps need an LLM + a transcript source,
which is the deferred AI piece. Activated when `CADENCE_GOOGLE_TOKEN` is set.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import httpx
from sqlalchemy import delete
from sqlalchemy.orm import Session

from sqlalchemy import select

from app.config import settings
from app.models.calendar import CalendarAccount, CalendarEvent, MeetingRecap
from app.services.calendar_service import MockCalendarService, week_bounds

_PALETTE = ["#3B7DD8", "#2E9E5B", "#E8833A", "#5A50E1", "#B45AF2", "#0E7C86", "#D95340"]


class GoogleApiError(RuntimeError):
    """Raised when the Google Calendar API returns an error (auth, quota, etc.)."""


class LiveCalendarService(MockCalendarService):
    """Live event import; recap() is inherited from the mock."""

    def import_events(self, db: Session) -> int:
        # Pull a wide window (±6 weeks) so the UI can navigate between weeks; the
        # GET endpoint slices out whichever week is being viewed.
        now = datetime.now(timezone.utc)
        data = self._api(
            "/calendars/primary/events",
            {
                "timeMin": (now - timedelta(weeks=6)).isoformat(),
                "timeMax": (now + timedelta(weeks=6)).isoformat(),
                "singleEvents": "true",
                "orderBy": "startTime",
                "maxResults": "250",
            },
        )
        items = data.get("items", [])

        # Replace the week's events (recaps FK events, so clear them first).
        db.execute(delete(MeetingRecap))
        db.execute(delete(CalendarEvent))

        count = 0
        for it in items:
            s = self._parse_dt(it.get("start", {}))
            e = self._parse_dt(it.get("end", {}))
            if not s or not e:
                continue
            attendees = []
            for a in it.get("attendees", []) or []:
                name = a.get("displayName") or a.get("email", "guest")
                email = a.get("email", name)
                attendees.append(
                    {"name": name, "initials": self._initials(name), "color": self._color(email)}
                )
            db.add(
                CalendarEvent(
                    title=it.get("summary") or "(no title)",
                    start=s,
                    end=e,
                    attendees=attendees,
                    meet_link=it.get("hangoutLink") or self._meet_link(it.get("conferenceData")),
                    location=it.get("location"),
                    description=it.get("description", "") or "",
                    source="google",
                )
            )
            count += 1

        # Record the real connected account (its id is the email address).
        acc = db.scalars(select(CalendarAccount)).first()
        if acc is not None:
            try:
                acc.email = self._api("/calendars/primary", {}).get("id")
            except GoogleApiError:
                pass

        db.commit()
        return count

    # --- helpers ---
    @classmethod
    def _api(cls, path: str, params: dict):
        resp = cls._request(path, params)
        # Access token expired → refresh once with the refresh token and retry.
        if resp.status_code == 401 and settings.google_refresh_token:
            cls._refresh()
            resp = cls._request(path, params)
        try:
            resp.raise_for_status()
            return resp.json()
        except httpx.HTTPStatusError as e:
            try:
                msg = e.response.json().get("error", {}).get("message", "")
            except Exception:
                msg = ""
            raise GoogleApiError(f"Google API {e.response.status_code}: {msg or path}") from e

    @staticmethod
    def _request(path: str, params: dict) -> httpx.Response:
        url = settings.google_calendar_api + path
        headers = {"Authorization": f"Bearer {settings.google_token}", "Accept": "application/json"}
        try:
            return httpx.get(url, headers=headers, params=params, timeout=15.0)
        except httpx.HTTPError as e:
            raise GoogleApiError(f"Could not reach Google: {e}") from e

    @staticmethod
    def _refresh() -> None:
        """Exchange the refresh token for a fresh access token (in-memory)."""
        try:
            resp = httpx.post(
                settings.google_token_uri,
                data={
                    "client_id": settings.google_client_id,
                    "client_secret": settings.google_client_secret,
                    "refresh_token": settings.google_refresh_token,
                    "grant_type": "refresh_token",
                },
                timeout=15.0,
            )
            resp.raise_for_status()
            token = resp.json().get("access_token")
            if token:
                settings.google_token = token
        except httpx.HTTPError as e:
            raise GoogleApiError(f"Google token refresh failed: {e}") from e

    @staticmethod
    def _parse_dt(obj: dict) -> datetime | None:
        v = obj.get("dateTime") or obj.get("date")
        if not v:
            return None
        if len(v) == 10:  # all-day (YYYY-MM-DD)
            return datetime.fromisoformat(v).replace(tzinfo=timezone.utc)
        return datetime.fromisoformat(v.replace("Z", "+00:00"))

    @staticmethod
    def _meet_link(conf: dict | None) -> str | None:
        for ep in (conf or {}).get("entryPoints", []) or []:
            if ep.get("entryPointType") == "video":
                return ep.get("uri")
        return None

    @staticmethod
    def _initials(name: str) -> str:
        parts = [p for p in name.replace("@", " ").replace(".", " ").split() if p]
        if len(parts) >= 2:
            return (parts[0][0] + parts[1][0]).upper()
        return (name[:2] or "?").upper()

    @staticmethod
    def _color(email: str) -> str:
        return _PALETTE[sum(ord(c) for c in email) % len(_PALETTE)]
