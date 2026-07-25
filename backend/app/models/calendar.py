"""Calendar models: a mock Google Calendar connection, events, and persisted
meeting recaps.

The "Google" connection is mocked behind a `MockCalendarService` seam; connecting
imports events into these rows. Recaps are generated (mock AI) and stored so they
persist in our DB, per the requirement.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base

if TYPE_CHECKING:
    pass


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class CalendarAccount(Base):
    """Single-row connection state for the (mock) Google Calendar link."""

    __tablename__ = "calendar_account"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    connected: Mapped[bool] = mapped_column(Boolean, default=False)
    email: Mapped[str | None] = mapped_column(String(160), nullable=True)
    connected_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class CalendarEvent(Base):
    __tablename__ = "calendar_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(String(200))
    start: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    end: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    # Attendees: list of {name, initials, color}
    attendees: Mapped[list[dict]] = mapped_column(JSON, default=list)
    meet_link: Mapped[str | None] = mapped_column(String(200), nullable=True)
    location: Mapped[str | None] = mapped_column(String(160), nullable=True)
    description: Mapped[str] = mapped_column(Text, default="")
    source: Mapped[str] = mapped_column(String(24), default="google")

    recap: Mapped[MeetingRecap | None] = relationship(
        "MeetingRecap", back_populates="event", uselist=False, cascade="all, delete-orphan"
    )


class MeetingRecap(Base):
    """A persisted AI recap of a meeting (kept on our DB)."""

    __tablename__ = "meeting_recaps"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    event_id: Mapped[int] = mapped_column(ForeignKey("calendar_events.id"))
    summary: Mapped[str] = mapped_column(Text)
    action_items: Mapped[list[str]] = mapped_column(JSON, default=list)
    decisions: Mapped[list[str]] = mapped_column(JSON, default=list)
    # Who produced the recap: "zoom" (AI Companion) or "cadence" (mock/Groq).
    source: Mapped[str] = mapped_column(String(24), default="cadence")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    event: Mapped[CalendarEvent] = relationship("CalendarEvent", back_populates="recap")
