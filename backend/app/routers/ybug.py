"""Ybug endpoints: receive visual feedback and turn it into board tickets.

- `POST /api/ybug/webhook` — real-time: Ybug POSTs each `feedback.created` here
  (HMAC-verified with the webhook secret). Needs a public URL to reach Cadence.
- `POST /api/ybug/sync` — poll the Ybug REST API for new feedback (works on
  localhost). Cursor = `YbugAccount.last_feedback_id` so tickets don't duplicate.
- `POST /api/ybug/simulate` — create one demo feedback ticket (offline demo).
- connect / disconnect / status.

Feedback lands as a `bug` ticket in the features space + active sprint (so it
shows on the Board), labelled `ybug`, with the full report in the description.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.db import get_db
from app.models.enums import IssueType, Space, Status
from app.models.issue import Issue
from app.models.sprint import Sprint
from app.models.ybug import YbugAccount
from app.routers.issues import _audit, _current_actor, _next_issue_key, _next_task_id
from app.schemas.entities import IssueOut
from app.schemas.ybug import YbugAccountOut, YbugSyncResult
from app.services import serializers as S
from app.services.ybug_service import (
    YbugService,
    build_issue_fields,
    get_ybug_service,
    sample_feedback,
)

router = APIRouter(prefix="/api/ybug", tags=["ybug"])


def _account(db: Session) -> YbugAccount:
    acc = db.scalars(select(YbugAccount)).first()
    if acc is None:
        acc = YbugAccount(connected=False)
        db.add(acc)
        db.commit()
        db.refresh(acc)
    return acc


def _active_sprint_id(db: Session) -> str | None:
    s = db.scalars(select(Sprint).where(Sprint.active.is_(True))).first()
    return s.id if s else None


def _create_ticket(db: Session, fb: dict) -> Issue:
    """Create a board ticket from one Ybug feedback payload."""
    fields = build_issue_fields(fb)
    space = Space(fields["space"]) if fields.get("space") in {s.value for s in Space} else Space.features
    labels = list(dict.fromkeys(["ybug", "feedback", *fields.get("labels", [])]))
    issue = Issue(
        key=_next_issue_key(db, space),
        type=IssueType(fields["type"]),
        title=fields["title"],
        description=fields["description"],
        task_id=_next_task_id(db),
        priority=fields["priority"],
        status=Status.todo,
        space=space,
        sprint_id=_active_sprint_id(db),
        labels=labels,
        comment_count=0,
    )
    db.add(issue)
    db.flush()
    _audit(db, issue.key, _current_actor(db), "created from Ybug feedback")
    return issue


def _verify_signature(raw: bytes, header: str) -> bool:
    secret = settings.ybug_webhook_secret
    if not secret:
        return True  # no secret configured (dev) → accept
    if not header:
        return False
    expected = "sha256=" + hmac.new(secret.encode(), raw, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, header)


@router.get("", response_model=YbugAccountOut)
def get_ybug(db: Session = Depends(get_db)) -> YbugAccountOut:
    return YbugAccountOut.model_validate(_account(db))


@router.post("/connect", response_model=YbugAccountOut)
def connect(
    db: Session = Depends(get_db),
    ybug: YbugService = Depends(get_ybug_service),
) -> YbugAccountOut:
    acc = _account(db)
    acc.connected = True
    acc.project_name = ybug.account_name()
    acc.connected_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(acc)
    return YbugAccountOut.model_validate(acc)


@router.post("/disconnect", response_model=YbugAccountOut)
def disconnect(db: Session = Depends(get_db)) -> YbugAccountOut:
    acc = _account(db)
    acc.connected = False
    db.commit()
    db.refresh(acc)
    return YbugAccountOut.model_validate(acc)


@router.post("/sync", response_model=YbugSyncResult)
def sync(
    db: Session = Depends(get_db),
    ybug: YbugService = Depends(get_ybug_service),
) -> YbugSyncResult:
    acc = _account(db)
    if not acc.connected:
        raise HTTPException(status_code=409, detail="Ybug is not connected")
    items = sorted(ybug.fetch_new(acc.last_feedback_id), key=lambda f: str(f.get("id", "")))
    keys: list[str] = []
    for fb in items:
        issue = _create_ticket(db, fb)
        keys.append(issue.key)
        acc.last_feedback_id = str(fb.get("id"))
        acc.ticket_count += 1
    db.commit()
    db.refresh(acc)
    return YbugSyncResult(account=YbugAccountOut.model_validate(acc), created=len(keys), keys=keys)


@router.post("/simulate", response_model=IssueOut)
def simulate(db: Session = Depends(get_db)) -> IssueOut:
    """Create one demo feedback ticket (as if a tester filed it in Ybug)."""
    acc = _account(db)
    fb = sample_feedback(f"sim-{uuid.uuid4().hex[:6]}", i=acc.ticket_count)
    issue = _create_ticket(db, fb)
    acc.ticket_count += 1
    db.commit()
    db.refresh(issue)
    return S.issue_out(issue)


@router.post("/webhook")
async def webhook(request: Request, db: Session = Depends(get_db)) -> dict:
    """Receive a Ybug feedback report and create a ticket (real-time path)."""
    raw = await request.body()
    if not _verify_signature(raw, request.headers.get("X-Ybug-Signature", "")):
        raise HTTPException(status_code=401, detail="Invalid signature")
    try:
        payload = json.loads(raw or b"{}")
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid JSON")
    event = payload.get("event")
    fb = payload.get("data") or payload  # payload may be wrapped or the feedback itself
    if event and event != "feedback.created":
        return {"ok": True, "skipped": event}
    acc = _account(db)
    issue = _create_ticket(db, fb)
    acc.ticket_count += 1
    if fb.get("id"):
        acc.last_feedback_id = str(fb["id"])
    db.commit()
    return {"ok": True, "key": issue.key}
