"""Calendar schemas (camelCase JSON)."""
from __future__ import annotations

from datetime import datetime

from app.schemas.common import CamelModel


class Attendee(CamelModel):
    name: str
    initials: str
    color: str


class MeetingRecapOut(CamelModel):
    id: int
    summary: str
    action_items: list[str] = []
    decisions: list[str] = []
    source: str = "cadence"
    created_at: datetime


class ZoomAccountOut(CamelModel):
    connected: bool
    account_name: str | None = None
    connected_at: datetime | None = None


class RecapActionItem(CamelModel):
    """Turn the Nth next-step of a recap into a Cadence ticket."""

    index: int


class CalendarEventOut(CamelModel):
    id: int
    title: str
    start: datetime
    end: datetime
    attendees: list[Attendee] = []
    meet_link: str | None = None
    location: str | None = None
    description: str = ""
    source: str = "google"
    recap: MeetingRecapOut | None = None


class CalendarAccountOut(CamelModel):
    connected: bool
    email: str | None = None
    connected_at: datetime | None = None


class CalendarOut(CamelModel):
    account: CalendarAccountOut
    week_start: datetime
    week_end: datetime
    events: list[CalendarEventOut]


class ConnectResult(CamelModel):
    account: CalendarAccountOut
    imported: int


class RecapResult(CamelModel):
    event: CalendarEventOut
    recap: MeetingRecapOut
