"""Ybug connection state. Ybug feedback (visual bug reports) becomes risr/crm
board tickets — in real time via the webhook, or by polling the Ybug REST API.
`last_feedback_id` is the poll cursor so we don't create duplicate tickets.
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class YbugAccount(Base):
    __tablename__ = "ybug_account"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    connected: Mapped[bool] = mapped_column(Boolean, default=False)
    project_name: Mapped[str | None] = mapped_column(String(160), nullable=True)
    connected_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # High-water mark of the last Ybug feedback id turned into a ticket (poll cursor).
    last_feedback_id: Mapped[str | None] = mapped_column(String(48), nullable=True)
    # Tickets created from Ybug feedback (for the Settings card count).
    ticket_count: Mapped[int] = mapped_column(Integer, default=0)
