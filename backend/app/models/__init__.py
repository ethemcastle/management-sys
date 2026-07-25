"""ORM models. Importing this package registers every table on `Base.metadata`."""
from __future__ import annotations

from app.models.audit import AuditLog
from app.models.calendar import CalendarAccount, CalendarEvent, MeetingRecap
from app.models.catalog import CatalogItem
from app.models.comment import Comment
from app.models.email import Email, IgnoreRule
from app.models.github import GitHubRepo, RepoBranch, RepoPullRequest
from app.models.enums import (
    CiStatus,
    EmailCategory,
    IgnoreField,
    IssueType,
    PrState,
    ReviewState,
    Role,
    Space,
    Status,
)
from app.models.issue import Issue
from app.models.member import TeamMember
from app.models.monday import MondayAccount, MondayBoard, MondayItem
from app.models.pull_request import PullRequest
from app.models.reviewer import Reviewer
from app.models.sprint import Sprint
from app.models.ybug import YbugAccount
from app.models.zoom import ZoomAccount

__all__ = [
    "AuditLog",
    "CalendarAccount",
    "CalendarEvent",
    "CatalogItem",
    "CiStatus",
    "Comment",
    "Email",
    "EmailCategory",
    "GitHubRepo",
    "IgnoreField",
    "IgnoreRule",
    "Issue",
    "IssueType",
    "MeetingRecap",
    "MondayAccount",
    "MondayBoard",
    "MondayItem",
    "RepoBranch",
    "RepoPullRequest",
    "PrState",
    "PullRequest",
    "ReviewState",
    "Reviewer",
    "Role",
    "Space",
    "Sprint",
    "Status",
    "TeamMember",
    "YbugAccount",
    "ZoomAccount",
]
