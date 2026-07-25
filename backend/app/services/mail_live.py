"""Live inbox implementation over IMAP (Gmail by default).

`LiveMailService` extends `MockMailService`, overriding `import_emails` to pull
real messages from an IMAP mailbox into the `emails` table (the same rows the
inbox UI already renders). The AI `recap` is inherited from the mock for now —
wiring it to the real LLM is the next step, exactly like the ticket summaries.

Activated when `CADENCE_MAIL_ADDRESS` + `CADENCE_MAIL_APP_PASSWORD` are set (see
`get_mail_service`). Uses only the Python stdlib (`imaplib`, `email`).
"""
from __future__ import annotations

import imaplib
import logging
import re
from email import message_from_bytes
from email.header import decode_header, make_header
from email.message import Message
from email.utils import parseaddr, parsedate_to_datetime

from sqlalchemy import delete
from sqlalchemy.orm import Session

from app.config import settings
from app.models.email import Email
from app.models.enums import EmailCategory
from app.services.mail_service import MockMailService

log = logging.getLogger("cadence.mail")

_PALETTE = ["#3B7DD8", "#2E9E5B", "#E8833A", "#5A50E1", "#B45AF2", "#0E7C86", "#D95340"]
_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"\s+")


class LiveMailService(MockMailService):
    """Real IMAP inbox import; recap() inherited from the mock (AI recap is next)."""

    def import_emails(self, db: Session) -> int:
        rows = self._fetch()
        # Replace the inbox with the freshly-fetched real messages.
        db.execute(delete(Email))
        for r in rows:
            db.add(Email(**r))
        db.commit()
        return len(rows)

    # --- IMAP ---
    @staticmethod
    def _fetch() -> list[dict]:
        host = settings.mail_imap_host
        limit = max(1, settings.mail_sync_limit)
        M = imaplib.IMAP4_SSL(host)
        try:
            M.login(settings.mail_address or "", settings.mail_app_password or "")
            M.select("INBOX", readonly=True)
            typ, data = M.search(None, "ALL")
            ids = data[0].split() if data and data[0] else []
            rows: list[dict] = []
            for num in reversed(ids[-limit:]):  # newest first
                typ, msgdata = M.fetch(num, "(FLAGS BODY.PEEK[])")
                if typ != "OK" or not msgdata:
                    continue
                raw, flagbytes = None, b""
                for part in msgdata:
                    if isinstance(part, tuple):
                        flagbytes += part[0] or b""
                        raw = part[1]
                    elif isinstance(part, (bytes, bytearray)):
                        flagbytes += part
                if not raw:
                    continue
                flags = imaplib.ParseFlags(flagbytes)
                rows.append(LiveMailService._to_row(message_from_bytes(raw), flags))
            return rows
        finally:
            try:
                M.logout()
            except Exception:
                pass

    # --- parsing ---
    @classmethod
    def _to_row(cls, msg: Message, flags: tuple) -> dict:
        name, addr = parseaddr(msg.get("From", ""))
        name = cls._decode(name) or (addr.split("@")[0] if addr else "Unknown")
        subject = cls._decode(msg.get("Subject", "")) or "(no subject)"
        body = cls._body(msg)
        preview = _WS_RE.sub(" ", body).strip()[:280]
        try:
            dt = parsedate_to_datetime(msg.get("Date"))
        except (TypeError, ValueError):
            dt = None
        seen = b"\\Seen" in flags
        return {
            "thread_id": (msg.get("Message-ID") or "")[:40] or None,
            "sender_name": name[:120],
            "sender_email": (addr or "unknown@unknown")[:160],
            "sender_color": _PALETTE[sum(ord(c) for c in (addr or name)) % len(_PALETTE)],
            "subject": subject[:255],
            "preview": preview,
            "body": body,
            "category": cls._category(addr or "", subject, body),
            "labels": [],
            "received_at": dt,
            "unread": not seen,
            "starred": b"\\Flagged" in flags,
        }

    @staticmethod
    def _decode(value: str | None) -> str:
        if not value:
            return ""
        try:
            return str(make_header(decode_header(value)))
        except Exception:
            return value

    @classmethod
    def _body(cls, msg: Message) -> str:
        plain, html = "", ""
        for part in msg.walk() if msg.is_multipart() else [msg]:
            ctype = part.get_content_type()
            if "attachment" in str(part.get("Content-Disposition", "")).lower():
                continue
            if ctype == "text/plain" and not plain:
                plain = cls._payload(part)
            elif ctype == "text/html" and not html:
                html = cls._payload(part)
        if plain.strip():
            return plain.strip()
        if html.strip():
            return _WS_RE.sub(" ", _TAG_RE.sub(" ", html)).strip()
        return ""

    @staticmethod
    def _payload(part: Message) -> str:
        try:
            data = part.get_payload(decode=True)
            if data is None:
                return ""
            return data.decode(part.get_content_charset() or "utf-8", errors="replace")
        except Exception:
            return ""

    @staticmethod
    def _category(sender_email: str, subject: str, body: str) -> EmailCategory:
        s, subj = sender_email.lower(), subject.lower()
        local = s.split("@")[0]
        if any(k in subj for k in ("alert", "incident", "failed", "failure", "error", "down", "urgent", "security", "breach")):
            return EmailCategory.alert
        if any(k in subj for k in ("invite", "invitation", "meeting", "calendar", "webinar", "zoom", ".ics")):
            return EmailCategory.meeting
        if "unsubscribe" in body.lower() or any(k in subj for k in ("newsletter", "digest", "weekly")) or "newsletter" in local:
            return EmailCategory.newsletter
        if any(k in local for k in ("noreply", "no-reply", "notification", "notifications", "mailer", "notify", "updates", "team@", "bot")) or any(
            k in s for k in ("github", "gitlab", "atlassian", "slack", "circleci", "vercel", "sentry", "linear")
        ):
            return EmailCategory.notification
        return EmailCategory.internal
