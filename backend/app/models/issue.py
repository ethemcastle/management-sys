"""Issue model — the central entity. A Feature is an Issue with type=epic."""
from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, backref, mapped_column, relationship

from app.db import Base
from app.models.enums import IssueType, Space, Status

if TYPE_CHECKING:
    from app.models.audit import AuditLog
    from app.models.comment import Comment
    from app.models.member import TeamMember
    from app.models.pull_request import PullRequest
    from app.models.sprint import Sprint


class Issue(Base):
    __tablename__ = "issues"

    key: Mapped[str] = mapped_column(String(24), primary_key=True)  # "CAD-142"
    type: Mapped[IssueType] = mapped_column(default=IssueType.task)
    title: Mapped[str] = mapped_column(String(255))
    priority: Mapped[int] = mapped_column(Integer, default=1)  # 0..3
    status: Mapped[Status] = mapped_column(default=Status.backlog)
    space: Mapped[Space] = mapped_column(default=Space.features)
    points: Mapped[int] = mapped_column(Integer, default=0)

    assignee_initials: Mapped[str | None] = mapped_column(ForeignKey("members.initials"))
    feature_key: Mapped[str | None] = mapped_column(ForeignKey("issues.key"))  # parent Feature
    sprint_id: Mapped[str | None] = mapped_column(ForeignKey("sprints.id"))

    # Feature-only display color (epics carry a color in the seed data).
    color: Mapped[str | None] = mapped_column(String(9), nullable=True)
    branch: Mapped[str | None] = mapped_column(String(160), nullable=True)
    blocked: Mapped[bool] = mapped_column(Boolean, default=False)
    review_requested: Mapped[bool] = mapped_column(Boolean, default=False)
    labels: Mapped[list[str]] = mapped_column(JSON, default=list)
    comment_count: Mapped[int] = mapped_column(Integer, default=0)

    # Extended "Information" fields. Owner is a second person alongside the
    # assignee (shown as "Dev"); product/component/target_release are free
    # categorisations; task_id is an external tracker id (e.g. RISR-0782).
    owner_initials: Mapped[str | None] = mapped_column(ForeignKey("members.initials"), nullable=True)
    product: Mapped[str | None] = mapped_column(String(80), nullable=True)
    component: Mapped[str | None] = mapped_column(String(80), nullable=True)
    task_id: Mapped[str | None] = mapped_column(String(48), nullable=True)
    target_release: Mapped[list[str]] = mapped_column(JSON, default=list)

    # Two-way monday.com link. `monday_item_id`/`monday_board_id` store monday's
    # STRING ids (board pks churn on re-pull). `monday_synced_at` doubles as a
    # "needs push" sentinel: NULL = a local change hasn't reached monday yet.
    monday_item_id: Mapped[str | None] = mapped_column(String(48), nullable=True)
    monday_board_id: Mapped[str | None] = mapped_column(String(48), nullable=True)
    monday_synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # The item's REAL monday status label + colour (kept as-is, not collapsed into
    # risr/crm's 5 statuses) so the UI can show "Stuck"/"Not Started"/etc. verbatim.
    monday_status: Mapped[str | None] = mapped_column(String(80), nullable=True)
    monday_status_color: Mapped[str | None] = mapped_column(String(9), nullable=True)
    # Every monday column on the item, verbatim: [{title, text, type, color?}] —
    # so the ticket shows each monday field exactly as monday has it.
    monday_fields: Mapped[list[dict]] = mapped_column(JSON, default=list)

    # Free-form markdown-ish description (rendered as blocks on the detail page).
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    assignee: Mapped[TeamMember | None] = relationship(
        "TeamMember", foreign_keys=[assignee_initials], lazy="joined"
    )
    owner: Mapped[TeamMember | None] = relationship(
        "TeamMember", foreign_keys=[owner_initials], lazy="joined"
    )
    sprint: Mapped[Sprint | None] = relationship("Sprint", lazy="joined")

    # Self-referential parent/child: feature.children == issues whose feature_key == feature.key
    children: Mapped[list[Issue]] = relationship(
        "Issue",
        backref=backref("feature", remote_side=[key]),
    )

    # An issue can accumulate multiple PRs (e.g. an AI-authored fix added to an
    # issue that already had one). `pr` (below) is the primary badge PR.
    prs: Mapped[list[PullRequest]] = relationship(
        "PullRequest",
        back_populates="issue",
        order_by="PullRequest.num",
        cascade="all, delete-orphan",
    )
    comments: Mapped[list[Comment]] = relationship(
        "Comment",
        back_populates="issue",
        order_by="Comment.created_at",
        cascade="all, delete-orphan",
    )
    audit_logs: Mapped[list[AuditLog]] = relationship(
        "AuditLog",
        order_by="AuditLog.created_at.desc()",
        cascade="all, delete-orphan",
    )

    @property
    def pr(self) -> PullRequest | None:
        """Primary PR for card/badge display: the first human PR, else the first."""
        if not self.prs:
            return None
        human = [p for p in self.prs if not p.ai_generated]
        return human[0] if human else self.prs[0]
