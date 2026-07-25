"""Recaps endpoints: Gemini meeting notes → a browsable list, with one-click
'next step → ticket'. The live source parses the Gemini emails over IMAP (the
same mailbox as the Inbox); a mock recap ships so the view is populated offline.
"""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.db import get_db
from app.models.enums import IssueType, Space, Status
from app.models.issue import Issue
from app.models.member import TeamMember
from app.models.recap import MeetingNote
from app.models.sprint import Sprint
from app.routers.issues import _audit, _current_actor, _next_issue_key, _next_task_id
from app.schemas.entities import IssueOut
from app.schemas.recap import MeetingNoteOut, RecapActionRef, RecapListOut, RecapSyncResult
from app.services import serializers as S
from app.services.gemini_recap import (
    GeminiRecapService,
    MockGeminiRecapService,
    get_gemini_recap_service,
)

router = APIRouter(prefix="/api/recaps", tags=["recaps"])

# Throttle live IMAP pulls so repeated loads don't hammer the mailbox.
_last_sync: dict[str, datetime | None] = {"t": None}


def _out(note: MeetingNote) -> MeetingNoteOut:
    return MeetingNoteOut.model_validate(note)


def _all(db: Session) -> list[MeetingNote]:
    return list(
        db.scalars(
            select(MeetingNote).order_by(MeetingNote.meeting_date.desc(), MeetingNote.id.desc())
        )
    )


def _upsert(db: Session, rec: dict) -> MeetingNote | None:
    """Insert a recap; skip (return None) if we've already stored it."""
    ext = rec.get("external_id")
    existing = None
    if ext:
        existing = db.scalars(select(MeetingNote).where(MeetingNote.external_id == ext)).first()
    else:
        existing = db.scalars(
            select(MeetingNote).where(
                MeetingNote.title == rec["title"],
                MeetingNote.meeting_date == rec.get("meeting_date"),
            )
        ).first()
    if existing is not None:
        return None
    note = MeetingNote(
        external_id=ext,
        title=rec["title"],
        meeting_date=rec.get("meeting_date"),
        summary=rec.get("summary", ""),
        sections=rec.get("sections", []),
        action_items=rec.get("action_items", []),
        attendees=rec.get("attendees", []),
        source=rec.get("source", "gemini"),
    )
    db.add(note)
    return note


def _sync(db: Session, service: GeminiRecapService) -> int:
    imported = 0
    for rec in service.fetch_recaps():
        if _upsert(db, rec) is not None:
            imported += 1
    if imported:
        db.commit()
    return imported


def _parse_dt(value) -> datetime | None:
    if not value:
        return None
    if isinstance(value, (int, float)):
        try:
            return datetime.fromtimestamp(value, tz=timezone.utc)
        except (ValueError, OSError):
            return None
    try:
        dt = datetime.fromisoformat(str(value).strip().replace("Z", "+00:00"))
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    except ValueError:
        return None


_ACTION_RE = re.compile(r"^\s*[-•*]?\s*(?:\[(?P<owner>[^\]]+)\])?\s*(?P<title>[^:]+?)(?::\s*(?P<detail>.+))?$")


def _norm_actions(raw) -> list[dict]:
    """Accept action items as strings ('[Owner] Title: detail') or dicts, from
    any notetaker, and normalise to {owner, title, detail}."""
    if isinstance(raw, str):
        raw = [l for l in raw.splitlines() if l.strip()]
    out: list[dict] = []
    for it in raw or []:
        if isinstance(it, dict):
            owner = (it.get("owner") or it.get("assignee") or it.get("who") or "").strip()
            title = (it.get("title") or it.get("text") or it.get("task") or it.get("name") or "").strip()
            detail = (it.get("detail") or it.get("description") or it.get("notes") or "").strip()
        elif isinstance(it, str):
            m = _ACTION_RE.match(it)
            if not m:
                continue
            owner = (m.group("owner") or "").strip()
            title = (m.group("title") or "").strip()
            detail = (m.group("detail") or "").strip()
        else:
            continue
        if title:
            out.append({"owner": owner, "title": title[:200], "detail": detail})
    return out


def _recap_from_payload(p: dict) -> dict:
    """Normalise any notetaker/webhook payload (Fireflies/Fathom/Otter/bridge)
    into a recap dict. Raw email/text is parsed via the Gemini parser."""
    body = p.get("body") or p.get("text") or p.get("raw")
    if body and not (p.get("summary") or p.get("action_items") or p.get("actionItems")):
        from app.services.gemini_recap import parse_gemini_email

        return parse_gemini_email(str(p.get("subject", "")), str(body), None)
    actions = _norm_actions(p.get("action_items") or p.get("actionItems") or p.get("tasks") or [])
    sections = [
        {"heading": (s.get("heading") or s.get("title") or "").strip(),
         "text": (s.get("text") or s.get("body") or "").strip()}
        for s in (p.get("sections") or []) if isinstance(s, dict)
    ]
    attendees = p.get("attendees") or [
        a["owner"] for a in actions if a["owner"] and a["owner"].lower() != "the group"
    ]
    if attendees and isinstance(attendees[0], dict):
        attendees = [a.get("name") or a.get("displayName") or a.get("email") for a in attendees]
    attendees = list(dict.fromkeys(a for a in attendees if a))
    return {
        "external_id": p.get("id") or p.get("external_id") or p.get("meeting_id"),
        "title": (p.get("title") or p.get("meeting") or p.get("name") or "Meeting recap").strip(),
        "meeting_date": _parse_dt(p.get("meeting_date") or p.get("date") or p.get("start")),
        "summary": (p.get("summary") or p.get("overview") or "").strip(),
        "sections": [s for s in sections if s["heading"] or s["text"]],
        "action_items": actions,
        "attendees": attendees,
        "source": p.get("source") or "webhook",
    }


def _active_sprint_id(db: Session) -> str | None:
    s = db.scalars(select(Sprint).where(Sprint.active.is_(True))).first()
    return s.id if s else None


_PALETTE = ["#0E7C86", "#B4530A", "#6D28D9", "#0F766E", "#9D174D", "#1D4ED8", "#B45309", "#4D7C0F"]


def _initials(name: str, taken: set[str]) -> str:
    words = [re.sub(r"[^A-Za-z]", "", w) for w in name.split()]
    words = [w for w in words if w]
    if not words:
        base = "?"
    elif len(words) == 1:
        base = words[0][:2].upper()
    else:
        base = (words[0][0] + words[1][0]).upper()
    ini, i = base, 1
    while ini in taken:
        ini = f"{base}{i}"[:4]
        i += 1
    return ini


def _member_for_owner(db: Session, owner: str) -> TeamMember | None:
    """Match a recap owner to a team member (creating one for a new name) so the
    ticket is assigned to the person named in the email."""
    owner = (owner or "").strip()
    if not owner or owner.lower() == "the group":
        return None
    members = list(db.scalars(select(TeamMember)))
    for m in members:
        if m.name.strip().lower() == owner.lower():
            return m
    member = TeamMember(
        initials=_initials(owner, {m.initials for m in members}),
        name=owner,
        color=_PALETTE[len(members) % len(_PALETTE)],
        role="developer",
        is_current_user=False,
    )
    db.add(member)
    db.flush()
    return member


def _ticket_from_item(db: Session, recap: MeetingNote, item: dict) -> Issue:
    """Create one Cadence task from a recap next step, assigned to its owner."""
    owner = (item.get("owner") or "").strip()
    title = (item.get("title") or "Follow-up").strip()
    detail = (item.get("detail") or "").strip()
    member = _member_for_owner(db, owner)
    who = f"**Owner:** {owner}\n\n" if owner and owner.lower() != "the group" else ""
    key = _next_issue_key(db, Space.features)
    issue = Issue(
        key=key,
        type=IssueType.task,
        title=title[:200],
        description=f"{who}Next step from the Gemini recap of “{recap.title}”.\n\n{detail}",
        task_id=_next_task_id(db),
        priority=1,
        status=Status.todo,
        space=Space.features,
        assignee_initials=member.initials if member else None,
        sprint_id=_active_sprint_id(db),
        labels=["meeting", "gemini"],
        comment_count=0,
    )
    db.add(issue)
    db.flush()
    _audit(db, key, _current_actor(db), f"created from the Gemini recap of “{recap.title}”")
    return issue


@router.get("", response_model=RecapListOut)
def list_recaps(
    db: Session = Depends(get_db),
    service: GeminiRecapService = Depends(get_gemini_recap_service),
) -> RecapListOut:
    live = bool(settings.recaps_script_url or (settings.mail_address and settings.mail_app_password))
    # Offline: seed the mock once. Live: re-pull from the mailbox on a short TTL.
    if not live:
        if not _all(db):
            _sync(db, service)
    else:
        now = datetime.now(timezone.utc)
        last = _last_sync["t"]
        if last is None or (now - last).total_seconds() > 30:
            try:
                _sync(db, service)
                _last_sync["t"] = now
            except Exception:
                pass  # keep whatever we have on a transient IMAP error
    return RecapListOut(
        connected=live,
        source=service.account_label(),
        recaps=[_out(n) for n in _all(db)],
    )


@router.post("/sync", response_model=RecapSyncResult)
def sync_recaps(
    db: Session = Depends(get_db),
    service: GeminiRecapService = Depends(get_gemini_recap_service),
) -> RecapSyncResult:
    imported = _sync(db, service)
    return RecapSyncResult(imported=imported, recaps=[_out(n) for n in _all(db)])


@router.post("/webhook")
async def recaps_webhook(request: Request, db: Session = Depends(get_db)) -> dict:
    """Universal intake: a notetaker (Fireflies/Fathom) or the Gemini bridge POSTs
    a recap here → parsed, stored, and its owners become assignable. Optional
    shared secret via the `X-Recaps-Token` header or `?token=` query param."""
    raw = await request.body()
    secret = settings.recaps_webhook_secret
    if secret:
        token = request.headers.get("X-Recaps-Token") or request.query_params.get("token", "")
        if token != secret:
            raise HTTPException(status_code=401, detail="Invalid token")
    try:
        payload = json.loads(raw or b"{}")
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid JSON")
    if not isinstance(payload, dict):
        raise HTTPException(status_code=400, detail="Expected a JSON object")
    rec = _recap_from_payload(payload)
    if not rec["action_items"] and not rec["summary"]:
        raise HTTPException(status_code=422, detail="No recap content in payload")
    note = _upsert(db, rec)
    db.commit()
    if note is None:
        return {"ok": True, "duplicate": True}
    db.refresh(note)
    return {"ok": True, "id": note.id, "title": note.title, "actionItems": len(note.action_items)}


@router.post("/simulate", response_model=MeetingNoteOut)
def simulate(db: Session = Depends(get_db)) -> MeetingNoteOut:
    """Insert the sample recap (offline demo)."""
    rec = MockGeminiRecapService().fetch_recaps()[0]
    stamp = datetime.now(timezone.utc).timestamp()
    rec["external_id"] = f"{rec['external_id']}-{stamp}"
    note = _upsert(db, rec)
    db.commit()
    db.refresh(note)
    return _out(note)


@router.post("/{recap_id}/action-item", response_model=IssueOut)
def action_item_to_ticket(
    recap_id: int, payload: RecapActionRef, db: Session = Depends(get_db)
) -> IssueOut:
    """Turn a recap's next step into a Cadence ticket, assigned to its owner."""
    recap = db.get(MeetingNote, recap_id)
    if recap is None:
        raise HTTPException(status_code=404, detail="Recap not found")
    items = recap.action_items or []
    if not (0 <= payload.index < len(items)):
        raise HTTPException(status_code=400, detail="Action item index out of range")
    issue = _ticket_from_item(db, recap, items[payload.index])
    db.commit()
    db.refresh(issue)
    return S.issue_out(issue)


@router.post("/{recap_id}/tickets", response_model=list[IssueOut])
def recap_to_tickets(recap_id: int, db: Session = Depends(get_db)) -> list[IssueOut]:
    """Turn every next step of a recap into a ticket, each assigned to its owner."""
    recap = db.get(MeetingNote, recap_id)
    if recap is None:
        raise HTTPException(status_code=404, detail="Recap not found")
    issues = [_ticket_from_item(db, recap, it) for it in (recap.action_items or [])]
    db.commit()
    return [S.issue_out(i) for i in issues]
