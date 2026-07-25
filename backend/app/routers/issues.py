"""Issue endpoints: list, detail, create, patch, create-branch, comment."""
from __future__ import annotations

import re

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import settings
from app.db import get_db
from app.deps import get_issue_or_404
from app.models.audit import AuditLog
from app.models.comment import Comment
from app.models.enums import IssueType, Space, Status
from app.models.issue import Issue
from app.models.member import TeamMember
from app.models.sprint import Sprint
from app.schemas.entities import (
    BranchResponse,
    CategoriesOut,
    CategoryValue,
    CommentOut,
    IssueDetailOut,
    IssueOut,
)
from app.schemas.requests import CommentCreate, IssueCreate, IssuePatch
from app.services import monday_sync
from app.services import serializers as S

router = APIRouter(prefix="/api/issues", tags=["issues"])


@router.get("", response_model=list[IssueOut])
def list_issues(
    db: Session = Depends(get_db),
    space: Space | None = Query(None),
    sprint: str | None = Query(None),
    assignee: str | None = Query(None),
    status: Status | None = Query(None),
    product: str | None = Query(None),
    component: str | None = Query(None),
    include_features: bool = Query(False, alias="includeFeatures"),
) -> list[IssueOut]:
    stmt = select(Issue)
    if space is not None:
        stmt = stmt.where(Issue.space == space)
    if not include_features:
        stmt = stmt.where(Issue.type != IssueType.epic)
    if sprint is not None:
        stmt = stmt.where(Issue.sprint_id == sprint)
    if assignee is not None:
        stmt = stmt.where(Issue.assignee_initials == assignee)
    if status is not None:
        stmt = stmt.where(Issue.status == status)
    if product is not None:
        stmt = stmt.where(Issue.product == product)
    if component is not None:
        stmt = stmt.where(Issue.component == component)
    issues = db.scalars(stmt.order_by(Issue.key)).all()
    return [S.issue_out(i) for i in issues]


@router.get("/categories", response_model=CategoriesOut)
def list_categories(db: Session = Depends(get_db)) -> CategoriesOut:
    """Distinct Product / Component values (with counts) for the sidebar category
    sections. Only non-empty values from non-epic issues."""

    def buckets(col) -> list[CategoryValue]:
        rows = db.execute(
            select(col, func.count())
            .where(col.is_not(None), col != "", Issue.type != IssueType.epic)
            .group_by(col)
            .order_by(col)
        ).all()
        return [CategoryValue(value=v, count=n) for v, n in rows]

    return CategoriesOut(products=buckets(Issue.product), components=buckets(Issue.component))


@router.get("/{key}", response_model=IssueDetailOut)
def get_issue(issue: Issue = Depends(get_issue_or_404)) -> IssueDetailOut:
    return S.issue_detail(issue)


@router.post("", response_model=IssueOut, status_code=201)
def create_issue(payload: IssueCreate, db: Session = Depends(get_db)) -> IssueOut:
    key = _next_issue_key(db, payload.space)
    issue = Issue(
        key=key,
        type=payload.type,
        title=payload.title,
        description=payload.description,
        task_id=_next_task_id(db),
        priority=payload.priority,
        status=payload.status or Status.backlog,
        space=payload.space,
        points=payload.points,
        assignee_initials=payload.assignee_initials,
        feature_key=payload.feature_key,
        sprint_id=payload.sprint_id,
        labels=payload.labels,
        product=payload.product,
        comment_count=0,
    )
    db.add(issue)
    db.flush()
    _audit(db, issue.key, _current_actor(db), "created this ticket")
    db.commit()
    db.refresh(issue)
    # Write-through: create the matching monday item (best-effort, non-blocking).
    monday_sync.push_create(db, issue, payload.monday_board_id, payload.monday_group_id)
    return S.issue_out(issue)


@router.patch("/{key}", response_model=IssueOut)
def patch_issue(
    payload: IssuePatch,
    issue: Issue = Depends(get_issue_or_404),
    db: Session = Depends(get_db),
) -> IssueOut:
    data = payload.model_dump(exclude_unset=True)
    actor = _current_actor(db)
    changed: set[str] = set()
    for field, value in data.items():
        if getattr(issue, field, None) == value:
            continue  # no-op edit — don't log it
        setattr(issue, field, value)
        changed.add(field)
        summary = _describe_change(db, field, value)
        if summary:
            _audit(db, issue.key, actor, summary)
    db.commit()
    db.refresh(issue)
    # Write-through: push changed shared fields to the linked monday item.
    if changed:
        monday_sync.push_patch(db, issue, changed)
    return S.issue_out(issue)


@router.post("/{key}/branch", response_model=BranchResponse)
def create_branch(
    issue: Issue = Depends(get_issue_or_404),
    db: Session = Depends(get_db),
) -> BranchResponse:
    branch = _branch_name(issue)
    issue.branch = branch
    db.commit()
    db.refresh(issue)
    return BranchResponse(branch=branch, issue=S.issue_out(issue))


@router.post("/{key}/comments", response_model=CommentOut, status_code=201)
def add_comment(
    payload: CommentCreate,
    issue: Issue = Depends(get_issue_or_404),
    db: Session = Depends(get_db),
) -> CommentOut:
    from app.models.member import TeamMember

    author = db.scalars(select(TeamMember).where(TeamMember.is_current_user.is_(True))).first()
    comment = Comment(
        issue_key=issue.key,
        author_initials=author.initials,
        kind="comment",
        body=payload.body,
    )
    db.add(comment)
    issue.comment_count += 1
    db.commit()
    db.refresh(comment)
    return S.comment_out(comment)


@router.delete("/{key}", status_code=204)
def delete_issue(
    issue: Issue = Depends(get_issue_or_404),
    db: Session = Depends(get_db),
) -> None:
    # Delete the linked monday item first (best-effort), then the issue.
    monday_sync.push_delete(db, issue)
    # Detach any children so a deleted Feature doesn't orphan its tasks' FK.
    for child in list(issue.children):
        child.feature_key = None
    db.delete(issue)
    db.commit()


# --- helpers ----------------------------------------------------------------
def _next_issue_key(db: Session, space: Space) -> str:
    prefix = "CAD" if space == Space.features else "SUP"
    keys = db.scalars(select(Issue.key).where(Issue.key.like(f"{prefix}-%"))).all()
    nums = [int(m.group(1)) for k in keys if (m := re.match(rf"{prefix}-(\d+)$", k))]
    nxt = (max(nums) + 1) if nums else 101
    return f"{prefix}-{nxt}"


def _next_task_id(db: Session) -> str:
    """Auto-generated, unique external Task ID, e.g. RISR-0001."""
    prefix = settings.task_id_prefix
    ids = db.scalars(select(Issue.task_id).where(Issue.task_id.like(f"{prefix}-%"))).all()
    nums = [int(m.group(1)) for t in ids if t and (m := re.match(rf"{prefix}-(\d+)$", t))]
    nxt = (max(nums) + 1) if nums else 1
    return f"{prefix}-{nxt:04d}"


# --- audit log ---
_STATUS_LABEL = {
    "backlog": "Backlog", "todo": "To Do", "inprogress": "In Progress",
    "review": "In Review", "done": "Done",
}
_PRIORITY_LABEL = ["Low", "Medium", "High", "Urgent"]


def _current_actor(db: Session) -> str | None:
    m = db.scalars(select(TeamMember).where(TeamMember.is_current_user.is_(True))).first()
    return m.initials if m else None


def _audit(db: Session, issue_key: str, actor: str | None, summary: str) -> None:
    db.add(AuditLog(issue_key=issue_key, actor_initials=actor, summary=summary))


def _describe_change(db: Session, field: str, new) -> str | None:
    """Human summary of a single field change for the audit log."""
    def member_name(ini: str | None) -> str:
        if not ini:
            return "Unassigned"
        m = db.get(TeamMember, ini)
        return m.name if m else ini

    if field == "status":
        return f"changed Status to {_STATUS_LABEL.get(getattr(new, 'value', new), new)}"
    if field == "assignee_initials":
        return f"changed Dev to {member_name(new)}"
    if field == "owner_initials":
        return f"changed Owner to {member_name(new)}"
    if field == "priority":
        return f"changed Priority to {_PRIORITY_LABEL[new] if isinstance(new, int) and 0 <= new < 4 else new}"
    if field == "points":
        return f"changed Points to {new}"
    if field == "sprint_id":
        s = db.get(Sprint, new) if new else None
        return f"changed Sprint to {s.name if s else 'None'}"
    if field == "blocked":
        return "marked as Blocked" if new else "cleared the Blocked flag"
    if field == "product":
        return f"set Product to {new}" if new else "cleared Product"
    if field == "component":
        return f"set Component to {new}" if new else "cleared Component"
    if field == "title":
        return f"renamed the ticket to “{new}”"
    if field == "description":
        return "edited the description"
    if field == "feature_key":
        f = db.get(Issue, new) if new else None
        return f"changed Epic to {f.title if f else 'None'}"
    if field == "target_release":
        return f"set Target Release to {', '.join(new)}" if new else "cleared Target Release"
    return f"updated {field}"


def _branch_name(issue: Issue) -> str:
    slug_words = re.sub(r"[^a-z0-9 ]", "", issue.title.lower()).split()
    slug = "-".join(slug_words[:4])
    prefix = {IssueType.bug: "fix", IssueType.epic: "epic"}.get(issue.type, "feat")
    return f"{prefix}/{issue.key.lower()}-{slug}".rstrip("-")
