"""Backlog / sprint-planning endpoint — grouped by sprint (features) or triage (support)."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.db import get_db
from app.models.enums import Space
from app.schemas.views import BacklogOut
from app.services import metrics

router = APIRouter(prefix="/api", tags=["backlog"])


@router.get("/backlog", response_model=BacklogOut)
def get_backlog(space: Space = Query(...), db: Session = Depends(get_db)) -> BacklogOut:
    return metrics.build_backlog(db, space)
