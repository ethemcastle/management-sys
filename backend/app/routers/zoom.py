"""Zoom endpoints: connect (mock or live), status, disconnect. Once connected,
the calendar recap flow pulls the AI Companion meeting summary from Zoom."""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models.zoom import ZoomAccount
from app.schemas.calendar import ZoomAccountOut
from app.services.zoom_service import ZoomService, get_zoom_service

router = APIRouter(prefix="/api/zoom", tags=["zoom"])


def _account(db: Session) -> ZoomAccount:
    acc = db.scalars(select(ZoomAccount)).first()
    if acc is None:
        acc = ZoomAccount(connected=False)
        db.add(acc)
        db.commit()
        db.refresh(acc)
    return acc


@router.get("", response_model=ZoomAccountOut)
def get_zoom(db: Session = Depends(get_db)) -> ZoomAccountOut:
    return ZoomAccountOut.model_validate(_account(db))


@router.post("/connect", response_model=ZoomAccountOut)
def connect(
    db: Session = Depends(get_db),
    zoom: ZoomService = Depends(get_zoom_service),
) -> ZoomAccountOut:
    acc = _account(db)
    acc.connected = True
    acc.account_name = zoom.account_name()
    acc.connected_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(acc)
    return ZoomAccountOut.model_validate(acc)


@router.post("/disconnect", response_model=ZoomAccountOut)
def disconnect(db: Session = Depends(get_db)) -> ZoomAccountOut:
    acc = _account(db)
    acc.connected = False
    db.commit()
    db.refresh(acc)
    return ZoomAccountOut.model_validate(acc)
