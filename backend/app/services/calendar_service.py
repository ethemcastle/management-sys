"""Calendar behind an interface.

`CalendarService` is the seam; `MockCalendarService` simulates a Google Calendar
connection: connecting imports a week of mock meetings (with Meet links), and
recaps are generated deterministically. A real Google Calendar implementation
swaps in here without any API/frontend change.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, time, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.calendar import CalendarEvent
from app.models.member import TeamMember


@dataclass
class RecapContent:
    summary: str
    action_items: list[str] = field(default_factory=list)
    decisions: list[str] = field(default_factory=list)


# (day offset from Monday, start hour, minute, duration min, title, attendee initials)
_TEMPLATES: list[tuple[int, int, int, int, str, list[str]]] = [
    (0, 9, 30, 30, "Daily standup", ["AL", "AR", "JC", "SL", "TB"]),
    (0, 14, 0, 60, "Onboarding v2 design review", ["MP", "AR", "AL"]),
    (1, 11, 0, 45, "Billing incident postmortem", ["JC", "DK", "MP"]),
    (2, 10, 0, 30, "Sprint 24 mid-sprint check-in", ["MP", "AL", "JC"]),
    (2, 15, 30, 30, "1:1 — Alex & Mira", ["AL", "MP"]),
    (3, 13, 0, 60, "Realtime sync architecture", ["SL", "AL", "TB"]),
    (4, 16, 0, 60, "Sprint 24 review & demo", ["AL", "AR", "JC", "MP", "DK", "SL", "TB"]),
]


def week_bounds(now: datetime | None = None) -> tuple[datetime, datetime]:
    now = now or datetime.now(timezone.utc)
    monday = (now - timedelta(days=now.weekday())).replace(
        hour=0, minute=0, second=0, microsecond=0
    )
    return monday, monday + timedelta(days=7)


class CalendarService(ABC):
    @abstractmethod
    def import_events(self, db: Session) -> int: ...

    @abstractmethod
    def recap(self, event: CalendarEvent) -> RecapContent: ...


class MockCalendarService(CalendarService):
    def import_events(self, db: Session) -> int:
        # Idempotent: if events already exist, treat connect as a no-op sync.
        existing = db.scalar(select(func.count()).select_from(CalendarEvent))
        if existing:
            return existing

        members = {m.initials: m for m in db.scalars(select(TeamMember))}
        monday, _ = week_bounds()
        count = 0
        for idx, (day, hour, minute, dur, title, initials) in enumerate(_TEMPLATES):
            start = (monday + timedelta(days=day)).replace(hour=hour, minute=minute)
            end = start + timedelta(minutes=dur)
            attendees = [
                {"name": members[i].name, "initials": i, "color": members[i].color}
                for i in initials
                if i in members
            ]
            db.add(
                CalendarEvent(
                    title=title,
                    start=start,
                    end=end,
                    attendees=attendees,
                    meet_link=f"https://meet.google.com/cad-{start.strftime('%m%d')}-{idx}",
                    location="Google Meet",
                    description=f"{title} — imported from Google Calendar.",
                    source="google",
                )
            )
            count += 1
        db.flush()
        return count

    def recap(self, event: CalendarEvent) -> RecapContent:
        names = [a.get("name", "") for a in (event.attendees or [])]
        firsts = [n.split()[0] for n in names if n]
        who = ", ".join(firsts[:3]) if firsts else "The team"
        owner = firsts[0] if firsts else "An owner"
        summary = (
            f"{who} met for “{event.title}”. The discussion stayed on time, key points were "
            f"captured, and owners were assigned. The group aligned on next steps and agreed to "
            f"follow up async on open questions."
        )
        action_items = [
            f"{owner} to follow up on the main blocker by end of week.",
            "Post the notes in the team channel and link the related issues.",
            "Confirm the decision with stakeholders before the next sync.",
        ]
        decisions = [f"Agreed to proceed with the plan discussed in “{event.title}”."]
        return RecapContent(summary=summary, action_items=action_items, decisions=decisions)


_mock_service: CalendarService = MockCalendarService()
_live_service: CalendarService | None = None


def get_calendar_service() -> CalendarService:
    """FastAPI dependency. Uses the live Google Calendar service when a token is
    configured (`CADENCE_GOOGLE_TOKEN`), otherwise the offline mock."""
    from app.config import settings

    if settings.google_token:
        global _live_service
        if _live_service is None:
            from app.services.calendar_live import LiveCalendarService

            _live_service = LiveCalendarService()
        return _live_service
    return _mock_service
