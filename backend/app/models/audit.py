"""Audit log: a chronological record of changes to an issue (field edits, status
changes, creation, AI PRs). Shown on the ticket so you can see who changed what."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base

if TYPE_CHECKING:
    from app.models.member import TeamMember


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    issue_key: Mapped[str] = mapped_column(ForeignKey("issues.key"))
    actor_initials: Mapped[str | None] = mapped_column(ForeignKey("members.initials"), nullable=True)
    summary: Mapped[str] = mapped_column(String(400))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    actor: Mapped[TeamMember | None] = relationship("TeamMember", lazy="joined")
