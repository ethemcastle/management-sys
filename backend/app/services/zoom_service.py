"""Zoom AI Companion recaps behind an interface.

`ZoomService` is the seam; `MockZoomService` simulates the AI Companion meeting
summary (overview + next steps + key details) so the recap flow is fully demoable
offline. `LiveZoomService` (Server-to-Server OAuth) swaps in via `get_zoom_service()`
when Zoom creds are configured — no API/frontend change. The recap shape reuses
`RecapContent` (summary / action_items / decisions), which maps 1:1 onto Zoom's
summary_overview / next_steps / summary_details.
"""
from __future__ import annotations

from abc import ABC, abstractmethod

from app.models.calendar import CalendarEvent
from app.services.calendar_service import RecapContent

MOCK_ACCOUNT_NAME = "Zoom · Acme Workplace"


class ZoomService(ABC):
    @abstractmethod
    def account_name(self) -> str: ...

    @abstractmethod
    def meeting_summary(self, event: CalendarEvent) -> RecapContent:
        """The AI Companion recap for a meeting (overview + next steps + details)."""


class MockZoomService(ZoomService):
    def account_name(self) -> str:
        return MOCK_ACCOUNT_NAME

    def meeting_summary(self, event: CalendarEvent) -> RecapContent:
        names = [a.get("name", "") for a in (event.attendees or [])]
        firsts = [n.split()[0] for n in names if n]
        who = ", ".join(firsts[:3]) if firsts else "The team"
        owner = firsts[0] if firsts else "An owner"
        second = firsts[1] if len(firsts) > 1 else owner
        overview = (
            f"{who} met for “{event.title}”. The group reviewed progress, surfaced "
            f"blockers, and aligned on the plan. AI Companion captured the key points "
            f"and the agreed next steps below."
        )
        next_steps = [
            f"{owner} to finish the main item discussed and share an update by end of week.",
            f"{second} to review the open pull request and leave feedback.",
            "Post the notes in the team channel and link the related tickets.",
        ]
        details = [
            f"Reviewed scope and timeline for “{event.title}”.",
            "Agreed to proceed with the approach discussed in the meeting.",
            "Flagged one risk to monitor before the next sync.",
        ]
        return RecapContent(summary=overview, action_items=next_steps, decisions=details)


_mock_service: ZoomService = MockZoomService()
_live_service: ZoomService | None = None


def get_zoom_service() -> ZoomService:
    """Uses the live Zoom service when Server-to-Server OAuth creds are configured
    (`CADENCE_ZOOM_CLIENT_ID`/`_SECRET`/`_ACCOUNT_ID`), otherwise the offline mock."""
    from app.config import settings

    if settings.zoom_client_id and settings.zoom_client_secret and settings.zoom_account_id:
        global _live_service
        if _live_service is None:
            from app.services.zoom_live import LiveZoomService

            _live_service = LiveZoomService()
        return _live_service
    return _mock_service
