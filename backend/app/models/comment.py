"""Comment model — comments and commit events on an issue's activity feed."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base

if TYPE_CHECKING:
    from app.models.issue import Issue
    from app.models.member import TeamMember


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Comment(Base):
    __tablename__ = "comments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    issue_key: Mapped[str] = mapped_column(ForeignKey("issues.key"))
    author_initials: Mapped[str] = mapped_column(ForeignKey("members.initials"))
    kind: Mapped[str] = mapped_column(String(16), default="comment")  # comment | commit
    body: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    issue: Mapped[Issue] = relationship("Issue", back_populates="comments")
    author: Mapped[TeamMember] = relationship("TeamMember", lazy="joined")
