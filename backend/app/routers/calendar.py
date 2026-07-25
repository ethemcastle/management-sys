"""Calendar endpoints: connect (mock Google), list week, per-meeting recap."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models.calendar import CalendarAccount, CalendarEvent, MeetingRecap
from app.models.enums import IssueType, Space, Status
from app.models.issue import Issue
from app.models.zoom import ZoomAccount
from app.routers.issues import _audit, _current_actor, _next_issue_key, _next_task_id
from app.schemas.calendar import (
    Attendee,
    CalendarAccountOut,
    CalendarEventOut,
    CalendarOut,
    ConnectResult,
    MeetingRecapOut,
    RecapActionItem,
    RecapResult,
)
from app.schemas.entities import IssueOut
from app.services import serializers as S
from app.services.calendar_service import CalendarService, get_calendar_service, week_bounds
from app.services.zoom_service import get_zoom_service

router = APIRouter(prefix="/api/calendar", tags=["calendar"])

CONNECTED_EMAIL = "alex.rivera@northwind.example"


def _account(db: Session) -> CalendarAccount:
    acc = db.scalars(select(CalendarAccount)).first()
    if acc is None:
        acc = CalendarAccount(connected=False)
        db.add(acc)
        db.commit()
        db.refresh(acc)
    return acc


def _recap_out(recap: MeetingRecap | None) -> MeetingRecapOut | None:
    if recap is None:
        return None
    return MeetingRecapOut(
        id=recap.id,
        summary=recap.summary,
        action_items=recap.action_items or [],
        decisions=recap.decisions or [],
        source=recap.source or "cadence",
        created_at=recap.created_at,
    )


def _event_out(e: CalendarEvent) -> CalendarEventOut:
    return CalendarEventOut(
        id=e.id,
        title=e.title,
        start=e.start,
        end=e.end,
        attendees=[Attendee(**a) for a in (e.attendees or [])],
        meet_link=e.meet_link,
        location=e.location,
        description=e.description,
        source=e.source,
        recap=_recap_out(e.recap),
    )


# Throttle live auto-refresh so repeated loads don't hammer the Google API.
_last_import: dict[str, datetime | None] = {"t": None}


@router.get("", response_model=CalendarOut)
def get_calendar(
    db: Session = Depends(get_db),
    calendar: CalendarService = Depends(get_calendar_service),
    week: str | None = Query(None, description="Monday of the week to show (YYYY-MM-DD)"),
) -> CalendarOut:
    from app.config import settings

    acc = _account(db)

    # Live mode: re-pull from Google on load (short TTL) so new events show up.
    if settings.google_token and acc.connected:
        now = datetime.now(timezone.utc)
        last = _last_import["t"]
        if last is None or (now - last).total_seconds() > 20:
            try:
                calendar.import_events(db)
                _last_import["t"] = now
            except Exception:
                pass  # keep whatever we have on a transient error

    if week:
        try:
            start = datetime.fromisoformat(week).replace(
                hour=0, minute=0, second=0, microsecond=0, tzinfo=timezone.utc
            )
            end = start + timedelta(days=7)
        except ValueError:
            start, end = week_bounds()
    else:
        start, end = week_bounds()

    events: list[CalendarEvent] = []
    if acc.connected:
        events = list(
            db.scalars(
                select(CalendarEvent)
                .where(CalendarEvent.start >= start, CalendarEvent.start < end)
                .order_by(CalendarEvent.start)
            )
        )
    return CalendarOut(
        account=CalendarAccountOut.model_validate(acc),
        week_start=start,
        week_end=end,
        events=[_event_out(e) for e in events],
    )


@router.post("/connect", response_model=ConnectResult)
def connect(
    db: Session = Depends(get_db),
    calendar: CalendarService = Depends(get_calendar_service),
) -> ConnectResult:
    from app.config import settings

    acc = _account(db)
    imported = calendar.import_events(db)
    acc.connected = True
    # Live service records the real connected account; only the mock uses the placeholder.
    if not settings.google_token:
        acc.email = CONNECTED_EMAIL
    acc.connected_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(acc)
    return ConnectResult(account=CalendarAccountOut.model_validate(acc), imported=imported)


@router.post("/disconnect", response_model=CalendarAccountOut)
def disconnect(db: Session = Depends(get_db)) -> CalendarAccountOut:
    acc = _account(db)
    acc.connected = False
    db.commit()
    db.refresh(acc)
    return CalendarAccountOut.model_validate(acc)


@router.get("/events/{event_id}", response_model=CalendarEventOut)
def get_event(event_id: int, db: Session = Depends(get_db)) -> CalendarEventOut:
    event = db.get(CalendarEvent, event_id)
    if event is None:
        raise HTTPException(status_code=404, detail="Event not found")
    return _event_out(event)


@router.post("/events/{event_id}/recap", response_model=RecapResult)
def recap_event(
    event_id: int,
    db: Session = Depends(get_db),
    calendar: CalendarService = Depends(get_calendar_service),
) -> RecapResult:
    event = db.get(CalendarEvent, event_id)
    if event is None:
        raise HTTPException(status_code=404, detail="Event not found")
    # Persist the recap on our DB; return the existing one if already generated.
    if event.recap is None:
        # When Zoom is connected, the recap is Zoom's AI Companion meeting summary;
        # otherwise it falls back to the built-in recap.
        zoom_acc = db.scalars(select(ZoomAccount)).first()
        if zoom_acc and zoom_acc.connected:
            content = get_zoom_service().meeting_summary(event)
            source = "zoom"
        else:
            content = calendar.recap(event)
            source = "cadence"
        recap = MeetingRecap(
            event_id=event.id,
            summary=content.summary,
            action_items=content.action_items,
            decisions=content.decisions,
            source=source,
        )
        db.add(recap)
        db.commit()
        db.refresh(event)
    return RecapResult(event=_event_out(event), recap=_recap_out(event.recap))


@router.post("/recaps/{recap_id}/action-item", response_model=IssueOut)
def action_item_to_ticket(
    recap_id: int, payload: RecapActionItem, db: Session = Depends(get_db)
) -> IssueOut:
    """Turn a recap's next-step (action item) into a Cadence ticket."""
    recap = db.get(MeetingRecap, recap_id)
    if recap is None:
        raise HTTPException(status_code=404, detail="Recap not found")
    items = recap.action_items or []
    if not (0 <= payload.index < len(items)):
        raise HTTPException(status_code=400, detail="Action item index out of range")
    text = items[payload.index]
    event = db.get(CalendarEvent, recap.event_id)
    meeting = event.title if event else "a meeting"
    key = _next_issue_key(db, Space.features)
    issue = Issue(
        key=key,
        type=IssueType.task,
        title=text[:200],
        description=(
            f"Next step captured by Zoom AI Companion in the recap of “{meeting}”.\n\n"
            f"{text}"
        ),
        task_id=_next_task_id(db),
        status=Status.todo,
        space=Space.features,
        labels=["meeting"],
        comment_count=0,
    )
    db.add(issue)
    db.flush()
    _audit(db, key, _current_actor(db), f"created from the Zoom recap of “{meeting}”")
    db.commit()
    db.refresh(issue)
    return S.issue_out(issue)
