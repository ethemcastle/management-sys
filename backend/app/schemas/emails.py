"""Inbox schemas (camelCase JSON)."""
from __future__ import annotations

from datetime import datetime

from app.models.enums import EmailCategory, IgnoreField
from app.schemas.common import CamelModel


class EmailOut(CamelModel):
    id: int
    sender_name: str
    sender_email: str
    sender_color: str
    subject: str
    preview: str
    category: EmailCategory
    labels: list[str] = []
    received_at: datetime
    unread: bool = True
    starred: bool = False
    ignored: bool = False  # derived: matches an active ignore rule


class EmailDetailOut(EmailOut):
    body: str = ""


class IgnoreRuleOut(CamelModel):
    id: int
    field: IgnoreField
    value: str
    active: bool = True
    matched: int = 0  # how many current emails this rule matches


class IgnoreRuleCreate(CamelModel):
    field: IgnoreField
    value: str


class CategoryBucket(CamelModel):
    category: EmailCategory
    label: str
    count: int
    color: str


class InboxOut(CamelModel):
    emails: list[EmailOut]
    categories: list[CategoryBucket]
    unread: int
    ignored_count: int
    connected: bool = False  # a real mailbox is configured (live IMAP)
    address: str | None = None  # the connected mailbox address (live mode)


class SyncResult(CamelModel):
    connected: bool
    address: str | None = None
    imported: int


class RecapGroup(CamelModel):
    category: EmailCategory
    label: str
    headline: str
    count: int


class InboxRecap(CamelModel):
    bullets: list[str]
    groups: list[RecapGroup]
    ignored_count: int
    summarized: int


class EmailPatch(CamelModel):
    unread: bool | None = None
    starred: bool | None = None
