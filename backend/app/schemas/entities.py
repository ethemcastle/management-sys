"""Response schemas for the core entities (denormalized, display-ready)."""
from __future__ import annotations

from datetime import datetime
from typing import Literal

from app.models.enums import (
    CiStatus,
    IssueType,
    PrState,
    ReviewState,
    Role,
    Space,
    Status,
)
from app.schemas.common import CamelModel


class MemberOut(CamelModel):
    initials: str
    name: str
    color: str
    role: Role
    is_current_user: bool = False


class MemberRef(CamelModel):
    """Slim member reference used inside issues/PRs/comments."""

    initials: str
    name: str
    color: str


class SpaceOut(CamelModel):
    id: str
    name: str
    sub: str
    kind: str


class SprintOut(CamelModel):
    id: str
    name: str
    range: str
    goal: str = ""
    days_left: int | None = None
    days_total: int
    capacity: int | None = None
    active: bool = False


class LabelOut(CamelModel):
    name: str
    color: str


class ReviewerOut(CamelModel):
    member: MemberRef
    state: ReviewState


class CheckOut(CamelModel):
    """A single CI check on a PR (real name + status from GitHub)."""

    name: str
    status: CiStatus


class PullRequestOut(CamelModel):
    num: int
    title: str
    branch: str | None = None
    state: PrState
    checks: CiStatus
    checks_detail: list[CheckOut] = []
    additions: int = 0
    deletions: int = 0
    files_changed: int = 0
    ai_generated: bool = False
    reviewers: list[ReviewerOut] = []


class FeatureRef(CamelModel):
    """Parent-feature chip shown on child issues."""

    key: str
    title: str
    color: str | None = None


class IssueOut(CamelModel):
    """Denormalized issue as consumed by boards, lists, cards, dashboards."""

    key: str
    type: IssueType
    title: str
    priority: int
    status: Status
    space: Space
    points: int
    assignee: MemberRef | None = None
    owner: MemberRef | None = None
    feature: FeatureRef | None = None
    sprint: str | None = None
    labels: list[LabelOut] = []
    branch: str | None = None
    blocked: bool = False
    review_requested: bool = False
    comment_count: int = 0
    pr: PullRequestOut | None = None
    # Extended "Information" fields.
    product: str | None = None
    component: str | None = None
    task_id: str | None = None
    target_release: list[str] = []
    # monday.com two-way sync link + state ('synced' | 'pending' | null).
    monday_item_id: str | None = None
    monday_board_id: str | None = None
    monday_synced_at: datetime | None = None
    sync_state: Literal["synced", "pending"] | None = None
    # The item's real monday status label + colour (verbatim, not collapsed).
    monday_status: str | None = None
    monday_status_color: str | None = None


class CategoryValue(CamelModel):
    """A distinct Product/Component value and how many issues carry it."""

    value: str
    count: int


class CategoriesOut(CamelModel):
    products: list[CategoryValue] = []
    components: list[CategoryValue] = []


class CatalogItemOut(CamelModel):
    id: int
    kind: str
    name: str


class CatalogItemCreate(CamelModel):
    kind: str
    name: str


class CatalogItemPatch(CamelModel):
    name: str


class CommentOut(CamelModel):
    id: int
    author: MemberRef
    kind: str = "comment"
    body: str
    created_at: datetime


class DescriptionBlock(CamelModel):
    type: Literal["heading", "paragraph", "list", "image", "link"]
    text: str | None = None
    items: list[str] | None = None
    url: str | None = None


class ChildProgress(CamelModel):
    done: int
    total: int


class AuditEntryOut(CamelModel):
    id: int
    actor: MemberRef | None = None
    summary: str
    created_at: datetime


class MondayFieldOut(CamelModel):
    """One monday column on the item, verbatim (status/priority carry a colour)."""

    title: str
    value: str
    type: str | None = None
    color: str | None = None


class IssueDetailOut(IssueOut):
    """Full issue detail: adds description blocks, activity, and epic children."""

    description: list[DescriptionBlock] = []
    comments: list[CommentOut] = []
    prs: list[PullRequestOut] = []  # all linked PRs for the Development section
    audit_log: list[AuditEntryOut] = []
    children: list[IssueOut] | None = None
    child_progress: ChildProgress | None = None
    monday_fields: list[MondayFieldOut] = []  # every monday column, verbatim


class BranchResponse(CamelModel):
    branch: str
    issue: IssueOut
