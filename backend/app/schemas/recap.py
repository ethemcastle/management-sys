"""Recap schemas (camelCase JSON) — Gemini meeting notes."""
from __future__ import annotations

from datetime import datetime

from app.schemas.common import CamelModel


class RecapSection(CamelModel):
    heading: str
    text: str = ""


class RecapAction(CamelModel):
    owner: str | None = None
    title: str
    detail: str = ""


class MeetingNoteOut(CamelModel):
    id: int
    title: str
    meeting_date: datetime | None = None
    summary: str = ""
    sections: list[RecapSection] = []
    action_items: list[RecapAction] = []
    attendees: list[str] = []
    source: str = "gemini"
    created_at: datetime


class RecapListOut(CamelModel):
    connected: bool
    source: str
    recaps: list[MeetingNoteOut] = []


class RecapSyncResult(CamelModel):
    imported: int
    recaps: list[MeetingNoteOut] = []


class RecapActionRef(CamelModel):
    index: int
