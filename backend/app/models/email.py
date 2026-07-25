"""Inbox models: Email messages and IgnoreRules.

Emails are mocked (a `MockMailService` seam mirrors `MockAiService`), so a real
Gmail/IMAP sync can populate these rows later without touching the API.
"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import JSON, Boolean, DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base
from app.models.enums import EmailCategory, IgnoreField


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Email(Base):
    __tablename__ = "emails"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    thread_id: Mapped[str | None] = mapped_column(String(40), nullable=True)
    sender_name: Mapped[str] = mapped_column(String(120))
    sender_email: Mapped[str] = mapped_column(String(160))
    sender_color: Mapped[str] = mapped_column(String(9))
    subject: Mapped[str] = mapped_column(String(255))
    preview: Mapped[str] = mapped_column(String(400))
    body: Mapped[str] = mapped_column(Text, default="")
    category: Mapped[EmailCategory] = mapped_column(default=EmailCategory.internal)
    labels: Mapped[list[str]] = mapped_column(JSON, default=list)
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    unread: Mapped[bool] = mapped_column(Boolean, default=True)
    starred: Mapped[bool] = mapped_column(Boolean, default=False)


class IgnoreRule(Base):
    """A rule that excludes matching emails from the recap (and mutes them)."""

    __tablename__ = "ignore_rules"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    field: Mapped[IgnoreField] = mapped_column(default=IgnoreField.category)
    value: Mapped[str] = mapped_column(String(160))
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    def matches(self, email: Email) -> bool:
        v = self.value.strip().lower()
        if not v:
            return False
        if self.field == IgnoreField.sender:
            return email.sender_email.lower() == v
        if self.field == IgnoreField.domain:
            return email.sender_email.lower().split("@")[-1] == v.lstrip("@")
        if self.field == IgnoreField.category:
            return email.category.value == v
        if self.field == IgnoreField.keyword:
            haystack = f"{email.subject} {email.preview} {email.body}".lower()
            return v in haystack
        return False
