"""Admin/maintenance endpoints. `reset-issues` clears all tickets (and their
comments/PRs/audit) while KEEPING team members, sprints, catalog, and the monday
connection — so the workspace can be repopulated from monday via Sync. The seed
gate keys on member count, so a members-preserving reset never reseeds demo data.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import delete, func, select, update
from sqlalchemy.orm import Session

from app.db import get_db
from app.models.audit import AuditLog
from app.models.comment import Comment
from app.models.issue import Issue
from app.models.monday import MondayItem
from app.models.pull_request import PullRequest
from app.models.reviewer import Reviewer
from app.schemas.common import CamelModel

router = APIRouter(prefix="/api/admin", tags=["admin"])


class ResetResult(CamelModel):
    deleted: int


@router.post("/reset-issues", response_model=ResetResult)
def reset_issues(db: Session = Depends(get_db)) -> ResetResult:
    n = db.scalar(select(func.count()).select_from(Issue)) or 0
    # FK-safe order (bulk delete bypasses ORM cascade).
    db.execute(delete(Reviewer))
    db.execute(delete(Comment))
    db.execute(delete(AuditLog))
    db.execute(delete(PullRequest))
    db.execute(delete(Issue))
    # Unlink monday items so a subsequent Sync re-imports them cleanly.
    db.execute(update(MondayItem).values(issue_key=None))
    db.commit()
    return ResetResult(deleted=n)
