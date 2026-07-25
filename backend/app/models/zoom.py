"""Zoom connection state. The recap itself is stored on `MeetingRecap`
(models/calendar.py); this row just tracks whether Zoom is connected so the UI
can show connect/disconnect and the recap flow knows to pull from Zoom's AI
Companion. Mocked behind `MockZoomService`; `LiveZoomService` swaps in when
Server-to-Server OAuth creds are configured.
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class ZoomAccount(Base):
    __tablename__ = "zoom_account"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    connected: Mapped[bool] = mapped_column(Boolean, default=False)
    account_name: Mapped[str | None] = mapped_column(String(160), nullable=True)
    connected_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
