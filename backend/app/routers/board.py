"""Board (Kanban) endpoint — server computes columns, counts, WIP limits."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.db import get_db
from app.models.enums import Space
from app.schemas.views import BoardOut
from app.services import metrics

router = APIRouter(prefix="/api", tags=["board"])


@router.get("/board", response_model=BoardOut)
def get_board(
    space: Space = Query(...),
    sprint: str | None = Query(None),
    db: Session = Depends(get_db),
) -> BoardOut:
    return metrics.build_board(db, space, sprint)
