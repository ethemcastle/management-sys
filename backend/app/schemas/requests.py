"""Request bodies (accept camelCase from the client)."""
from __future__ import annotations

from app.models.enums import IssueType, Space, Status
from app.schemas.common import CamelModel


class IssueCreate(CamelModel):
    type: IssueType
    title: str
    description: str | None = None
    priority: int = 1
    status: Status | None = None
    space: Space
    points: int = 0
    assignee_initials: str | None = None
    feature_key: str | None = None
    sprint_id: str | None = None
    labels: list[str] = []
    product: str | None = None
    # Optional monday.com target: create the matching item on this board/group.
    monday_board_id: str | None = None
    monday_group_id: str | None = None


class IssuePatch(CamelModel):
    status: Status | None = None
    assignee_initials: str | None = None
    owner_initials: str | None = None
    priority: int | None = None
    points: int | None = None
    sprint_id: str | None = None
    feature_key: str | None = None
    title: str | None = None
    description: str | None = None
    blocked: bool | None = None
    product: str | None = None
    component: str | None = None
    target_release: list[str] | None = None
    # task_id is auto-generated + unique — not user-editable (no patch field).


class CommentCreate(CamelModel):
    body: str


class AnswerRequest(CamelModel):
    question: str


class AssistantContext(CamelModel):
    view: str
    space: Space
    sprint: str | None = None


class AssistantRequest(CamelModel):
    question: str
    context: AssistantContext
