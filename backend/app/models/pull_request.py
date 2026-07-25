"""PullRequest model — 1:1 with an Issue, referenced by its PR number."""
from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import Boolean, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base
from app.models.enums import CiStatus, PrState

if TYPE_CHECKING:
    from app.models.issue import Issue
    from app.models.reviewer import Reviewer


class PullRequest(Base):
    __tablename__ = "pull_requests"

    num: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=False)  # 812
    issue_key: Mapped[str] = mapped_column(ForeignKey("issues.key"))
    title: Mapped[str] = mapped_column(String(255))
    branch: Mapped[str | None] = mapped_column(String(160), nullable=True)
    state: Mapped[PrState] = mapped_column(default=PrState.open)
    checks: Mapped[CiStatus] = mapped_column(default=CiStatus.pending)
    additions: Mapped[int] = mapped_column(Integer, default=0)
    deletions: Mapped[int] = mapped_column(Integer, default=0)
    files_changed: Mapped[int] = mapped_column(Integer, default=0)
    ai_generated: Mapped[bool] = mapped_column(Boolean, default=False)

    issue: Mapped[Issue] = relationship("Issue", back_populates="prs")
    reviewers: Mapped[list[Reviewer]] = relationship(
        "Reviewer", lazy="joined", cascade="all, delete-orphan"
    )
