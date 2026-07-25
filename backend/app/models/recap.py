"""Standalone meeting recaps from Gemini ("Take notes for me" emails).

Unlike MeetingRecap (tied to a calendar event), these stand on their own — the
Recaps view lists them directly. The live source parses the Gemini notes emails
over IMAP; a mock seed ships for offline use.
"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import JSON, DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class MeetingNote(Base):
    __tablename__ = "meeting_notes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    external_id: Mapped[str | None] = mapped_column(String(255), nullable=True, unique=True)
    title: Mapped[str] = mapped_column(String(200))
    meeting_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    summary: Mapped[str] = mapped_column(Text, default="")
    sections: Mapped[list[dict]] = mapped_column(JSON, default=list)       # [{heading, text}]
    action_items: Mapped[list[dict]] = mapped_column(JSON, default=list)   # [{owner, title, detail}]
    attendees: Mapped[list[str]] = mapped_column(JSON, default=list)
    source: Mapped[str] = mapped_column(String(24), default="gemini")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
