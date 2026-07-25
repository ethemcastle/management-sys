"""Mail behind an interface.

`MailService` is the seam; `MockMailService` ships by default and produces a
deterministic inbox recap. A real Gmail/IMAP implementation can replace it
without changing the API or the frontend.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.email import Email
from app.models.enums import EmailCategory

# label + token-ish color per category (kept here as the single source of truth)
CATEGORY_META: dict[EmailCategory, tuple[str, str]] = {
    EmailCategory.customer: ("Customer", "#3B7DD8"),
    EmailCategory.internal: ("Internal", "#5A50E1"),
    EmailCategory.notification: ("Notifications", "#9A998F"),
    EmailCategory.newsletter: ("Newsletters", "#95948B"),
    EmailCategory.alert: ("Alerts", "#D95340"),
    EmailCategory.meeting: ("Meetings", "#8B5CF6"),
}


@dataclass
class RecapGroupData:
    category: EmailCategory
    label: str
    headline: str
    count: int


@dataclass
class RecapData:
    bullets: list[str]
    groups: list[RecapGroupData] = field(default_factory=list)
    summarized: int = 0
    ignored_count: int = 0


class MailService(ABC):
    @abstractmethod
    def recap(self, emails: list[Email], ignored_count: int) -> RecapData: ...

    @abstractmethod
    def import_emails(self, db: Session) -> int:
        """Sync real messages into the `emails` table. Returns the count now present."""
        ...


class MockMailService(MailService):
    """Deterministic mock recap: groups the (non-ignored) inbox by category."""

    def import_emails(self, db: Session) -> int:
        # No real mailbox in mock mode — the seeded inbox is the data. No-op sync.
        return db.scalar(select(func.count()).select_from(Email)) or 0

    _VERBS = {
        EmailCategory.customer: "need replies",
        EmailCategory.internal: "from the team",
        EmailCategory.notification: "from your tools",
        EmailCategory.newsletter: "to skim later",
        EmailCategory.alert: "need attention now",
        EmailCategory.meeting: "about upcoming meetings",
    }

    def recap(self, emails: list[Email], ignored_count: int) -> RecapData:
        by_cat: dict[EmailCategory, list[Email]] = {}
        for e in emails:
            by_cat.setdefault(e.category, []).append(e)

        # Order by urgency then volume.
        priority = [
            EmailCategory.alert,
            EmailCategory.customer,
            EmailCategory.internal,
            EmailCategory.meeting,
            EmailCategory.notification,
            EmailCategory.newsletter,
        ]
        ordered = sorted(
            by_cat.items(),
            key=lambda kv: (priority.index(kv[0]) if kv[0] in priority else 99, -len(kv[1])),
        )

        groups: list[RecapGroupData] = []
        bullets: list[str] = []
        for cat, items in ordered:
            label, _ = CATEGORY_META[cat]
            sample = items[0].subject
            headline = f"{len(items)} {label.lower()} {self._VERBS[cat]} — e.g. “{sample}”."
            groups.append(RecapGroupData(cat, label, headline, len(items)))
            if cat in (EmailCategory.alert, EmailCategory.customer, EmailCategory.internal):
                bullets.append(headline)

        if not bullets and groups:
            bullets.append(groups[0].headline)

        if ignored_count:
            bullets.append(f"Skipped {ignored_count} email(s) matching your ignore rules.")

        top = next((c for c, _ in ordered), None)
        if top == EmailCategory.alert:
            net = "Net: clear the alerts first, then the customer threads."
        elif top == EmailCategory.customer:
            net = "Net: reply to the customer threads first; the rest can wait."
        else:
            net = "Net: nothing on fire — a quick pass will clear the inbox."
        bullets.append(net)

        return RecapData(
            bullets=bullets,
            groups=groups,
            summarized=len(emails),
            ignored_count=ignored_count,
        )


_service: MailService = MockMailService()
_live_service: MailService | None = None


def get_mail_service() -> MailService:
    """FastAPI dependency. Uses the live IMAP mail service when a mailbox address +
    app password are configured (`CADENCE_MAIL_ADDRESS`/`CADENCE_MAIL_APP_PASSWORD`),
    otherwise the seeded offline mock."""
    from app.config import settings

    if settings.mail_address and settings.mail_app_password:
        global _live_service
        if _live_service is None:
            from app.services.mail_live import LiveMailService

            _live_service = LiveMailService()
        return _live_service
    return _service
