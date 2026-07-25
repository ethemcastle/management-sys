"""Reviewer model — a team member's review state on a PR."""
from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base
from app.models.enums import ReviewState

if TYPE_CHECKING:
    from app.models.member import TeamMember


class Reviewer(Base):
    __tablename__ = "reviewers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    pr_num: Mapped[int] = mapped_column(ForeignKey("pull_requests.num"))
    member_initials: Mapped[str] = mapped_column(ForeignKey("members.initials"))
    state: Mapped[ReviewState] = mapped_column(default=ReviewState.pending)

    member: Mapped[TeamMember] = relationship("TeamMember", lazy="joined")
