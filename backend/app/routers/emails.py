"""Inbox endpoints: list, detail, patch, AI recap, sync, and ignore-rule management."""
from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models.email import Email, IgnoreRule
from app.models.enums import EmailCategory
from app.schemas.emails import (
    CategoryBucket,
    EmailDetailOut,
    EmailOut,
    EmailPatch,
    IgnoreRuleCreate,
    IgnoreRuleOut,
    InboxOut,
    InboxRecap,
    RecapGroup,
    SyncResult,
)
from app.services.mail_service import CATEGORY_META, MailService, get_mail_service

router = APIRouter(prefix="/api/emails", tags=["emails"])
log = logging.getLogger("cadence.mail")

# Import the real mailbox once per process on first load (so connecting shows real
# mail immediately); further refreshes are on-demand via POST /sync — which keeps
# read/star state stable between explicit syncs.
_auto_synced = {"done": False}


def _active_rules(db: Session) -> list[IgnoreRule]:
    return list(db.scalars(select(IgnoreRule).where(IgnoreRule.active.is_(True))))


def _is_ignored(email: Email, rules: list[IgnoreRule]) -> bool:
    return any(r.matches(email) for r in rules)


def _email_out(email: Email, ignored: bool) -> EmailOut:
    return EmailOut(
        id=email.id,
        sender_name=email.sender_name,
        sender_email=email.sender_email,
        sender_color=email.sender_color,
        subject=email.subject,
        preview=email.preview,
        category=email.category,
        labels=email.labels or [],
        received_at=email.received_at,
        unread=email.unread,
        starred=email.starred,
        ignored=ignored,
    )


def _all_emails(db: Session) -> list[Email]:
    return list(db.scalars(select(Email).order_by(Email.received_at.desc())))


@router.get("", response_model=InboxOut)
def inbox(
    db: Session = Depends(get_db),
    mail: MailService = Depends(get_mail_service),
    category: EmailCategory | None = Query(None),
    include_ignored: bool = Query(False, alias="includeIgnored"),
) -> InboxOut:
    from app.config import settings

    connected = bool(settings.mail_address and settings.mail_app_password)
    # First load after a real mailbox is configured: pull it in once.
    if connected and not _auto_synced["done"]:
        try:
            mail.import_emails(db)
        except Exception as e:  # bad password, unreachable host, etc.
            log.warning("inbox auto-sync failed: %s", e)
        _auto_synced["done"] = True

    rules = _active_rules(db)
    emails = _all_emails(db)
    flags = {e.id: _is_ignored(e, rules) for e in emails}

    # Category buckets (over non-ignored emails) for the filter rail.
    buckets: list[CategoryBucket] = []
    for cat in EmailCategory:
        label, color = CATEGORY_META[cat]
        count = sum(1 for e in emails if e.category == cat and not flags[e.id])
        if count:
            buckets.append(CategoryBucket(category=cat, label=label, count=count, color=color))

    shown = emails
    if category is not None:
        shown = [e for e in shown if e.category == category]
    ignored_count = sum(1 for e in shown if flags[e.id])
    if not include_ignored:
        shown = [e for e in shown if not flags[e.id]]

    unread = sum(1 for e in shown if e.unread and not flags[e.id])
    return InboxOut(
        emails=[_email_out(e, flags[e.id]) for e in shown],
        categories=buckets,
        unread=unread,
        ignored_count=ignored_count,
        connected=connected,
        address=settings.mail_address if connected else None,
    )


@router.post("/sync", response_model=SyncResult)
def sync_inbox(
    db: Session = Depends(get_db),
    mail: MailService = Depends(get_mail_service),
) -> SyncResult:
    """Pull the latest messages from the connected mailbox into the inbox. In mock
    mode (no mailbox configured) this is a no-op that reports the seeded count."""
    from app.config import settings

    connected = bool(settings.mail_address and settings.mail_app_password)
    try:
        imported = mail.import_emails(db)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Mailbox sync failed: {e}") from e
    _auto_synced["done"] = True
    return SyncResult(
        connected=connected,
        address=settings.mail_address if connected else None,
        imported=imported,
    )


@router.get("/ignore-rules", response_model=list[IgnoreRuleOut])
def list_rules(db: Session = Depends(get_db)) -> list[IgnoreRuleOut]:
    rules = list(db.scalars(select(IgnoreRule).order_by(IgnoreRule.created_at)))
    emails = _all_emails(db)
    out = []
    for r in rules:
        matched = sum(1 for e in emails if r.matches(e))
        out.append(
            IgnoreRuleOut(id=r.id, field=r.field, value=r.value, active=r.active, matched=matched)
        )
    return out


@router.post("/ignore-rules", response_model=IgnoreRuleOut, status_code=201)
def create_rule(payload: IgnoreRuleCreate, db: Session = Depends(get_db)) -> IgnoreRuleOut:
    rule = IgnoreRule(field=payload.field, value=payload.value.strip(), active=True)
    db.add(rule)
    db.commit()
    db.refresh(rule)
    matched = sum(1 for e in _all_emails(db) if rule.matches(e))
    return IgnoreRuleOut(id=rule.id, field=rule.field, value=rule.value, active=rule.active, matched=matched)


@router.delete("/ignore-rules/{rule_id}", status_code=204)
def delete_rule(rule_id: int, db: Session = Depends(get_db)) -> None:
    rule = db.get(IgnoreRule, rule_id)
    if rule is None:
        raise HTTPException(status_code=404, detail="Rule not found")
    db.delete(rule)
    db.commit()


@router.post("/recap", response_model=InboxRecap)
def recap(
    db: Session = Depends(get_db),
    mail: MailService = Depends(get_mail_service),
) -> InboxRecap:
    rules = _active_rules(db)
    emails = _all_emails(db)
    included = [e for e in emails if not _is_ignored(e, rules)]
    ignored_count = len(emails) - len(included)
    data = mail.recap(included, ignored_count)
    return InboxRecap(
        bullets=data.bullets,
        groups=[
            RecapGroup(category=g.category, label=g.label, headline=g.headline, count=g.count)
            for g in data.groups
        ],
        ignored_count=data.ignored_count,
        summarized=data.summarized,
    )


@router.get("/{email_id}", response_model=EmailDetailOut)
def get_email(email_id: int, db: Session = Depends(get_db)) -> EmailDetailOut:
    email = db.get(Email, email_id)
    if email is None:
        raise HTTPException(status_code=404, detail="Email not found")
    ignored = _is_ignored(email, _active_rules(db))
    base = _email_out(email, ignored)
    return EmailDetailOut(**base.model_dump(by_alias=False), body=email.body)


@router.patch("/{email_id}", response_model=EmailOut)
def patch_email(email_id: int, payload: EmailPatch, db: Session = Depends(get_db)) -> EmailOut:
    email = db.get(Email, email_id)
    if email is None:
        raise HTTPException(status_code=404, detail="Email not found")
    data = payload.model_dump(exclude_unset=True)
    for k, v in data.items():
        setattr(email, k, v)
    db.commit()
    db.refresh(email)
    return _email_out(email, _is_ignored(email, _active_rules(db)))
