"""Shared FastAPI dependencies."""
from __future__ import annotations

from fastapi import Depends, HTTPException, Path
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models.issue import Issue
from app.models.member import TeamMember


def get_current_user(db: Session = Depends(get_db)) -> TeamMember:
    """The signed-in user. Auth is out of scope for the prototype; the seam is
    here so a real auth layer can replace it without touching the routers.
    """
    user = db.scalars(select(TeamMember).where(TeamMember.is_current_user.is_(True))).first()
    if user is None:
        raise HTTPException(status_code=500, detail="No current user configured")
    return user


def get_issue_or_404(key: str = Path(...), db: Session = Depends(get_db)) -> Issue:
    issue = db.get(Issue, key)
    if issue is None:
        raise HTTPException(status_code=404, detail=f"Issue {key} not found")
    return issue
