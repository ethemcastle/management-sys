"""Sprint endpoints — health metrics and starting a sprint."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models.enums import Space
from app.models.sprint import Sprint
from app.schemas.entities import SprintOut
from app.schemas.views import SprintHealthOut
from app.services import metrics

router = APIRouter(prefix="/api/sprints", tags=["sprints"])


@router.get("/{sprint_id}/health", response_model=SprintHealthOut)
def sprint_health(
    sprint_id: str,
    space: Space = Query(Space.features),
    db: Session = Depends(get_db),
) -> SprintHealthOut:
    return metrics.sprint_health(db, space, sprint_id)


@router.post("/{sprint_id}/start", response_model=SprintOut)
def start_sprint(sprint_id: str, db: Session = Depends(get_db)) -> SprintOut:
    """Make this the active sprint (deactivating any other)."""
    target = db.get(Sprint, sprint_id)
    if target is None:
        raise HTTPException(status_code=404, detail=f"Sprint {sprint_id} not found")
    for s in db.scalars(select(Sprint)):
        s.active = s.id == sprint_id
    if target.days_left is None:
        target.days_left = target.days_total
    db.commit()
    db.refresh(target)
    return SprintOut.model_validate(target)
