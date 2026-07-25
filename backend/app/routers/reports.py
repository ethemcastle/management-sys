"""Reports & analytics endpoint — stat cards, burndown, velocity, distribution."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.db import get_db
from app.models.enums import Space
from app.schemas.views import ReportsOut
from app.services import metrics

router = APIRouter(prefix="/api", tags=["reports"])


@router.get("/reports", response_model=ReportsOut)
def get_reports(
    space: Space = Query(Space.features),
    sprint: str | None = Query(None),
    db: Session = Depends(get_db),
) -> ReportsOut:
    return metrics.build_reports(db, space, sprint)
