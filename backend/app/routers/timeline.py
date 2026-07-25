"""Timeline (roadmap) endpoint — Features space only."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.db import get_db
from app.models.enums import Space
from app.schemas.views import TimelineOut
from app.services import metrics

router = APIRouter(prefix="/api", tags=["timeline"])


@router.get("/timeline", response_model=TimelineOut)
def get_timeline(space: Space = Query(Space.features), db: Session = Depends(get_db)) -> TimelineOut:
    return metrics.build_timeline(db, space)
