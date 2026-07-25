"""Gemini meeting recaps behind a service seam.

Google Meet's "Take notes for me" (Gemini) emails a structured recap after each
meeting (from gemini-notes@google.com). `parse_gemini_email` turns that email
into a recap: title, date, a Summary (intro + sections), and owner-tagged
"Suggested next steps" (each a candidate ticket).

- `MockGeminiRecapService` — a realistic sample recap so the Recaps view works
  offline / before a mailbox is configured.
- `LiveGeminiRecapService` — pulls the Gemini emails over IMAP (the same mailbox
  used for the Inbox) and parses them. Enabled when `CADENCE_MAIL_ADDRESS` +
  `CADENCE_MAIL_APP_PASSWORD` are set.
"""
from __future__ import annotations

import re
from abc import ABC, abstractmethod
from datetime import datetime, timezone

import httpx

GEMINI_SENDER = "gemini-notes@google.com"

_STEP_RE = re.compile(
    r"^\s*[\-•\t ]*(?:\[(?P<owner>[^\]]+)\]\s*)?(?P<title>[^:]+?):\s*(?P<detail>.+)$"
)
_TITLE_RE = re.compile(r"Notes\s*(?:from|:)\s*['‘’\"](?P<t>[^'‘’\"]+)")
_DATE_RE = re.compile(r"auto-generated on\s+(?P<d>[A-Za-z]+ \d{1,2},? \d{4})")
_MONTHS = {
    m: i for i, m in enumerate(
        ["january", "february", "march", "april", "may", "june", "july",
         "august", "september", "october", "november", "december"], 1)
}
_END_MARKERS = (
    "We've updated the Decisions", "What do you think", "Meeting records",
    "Is the 'Next steps'", "Google LLC", "You have received this email",
)


def _lines(body: str) -> list[str]:
    return [l.strip() for l in body.replace("\r\n", "\n").split("\n")]


def _extract_title(subject: str, body: str) -> str:
    for src in (subject or "", body or ""):
        if (m := _TITLE_RE.search(src)):
            return m.group("t").strip()
    return "Meeting recap"


def _extract_date(body: str, fallback: datetime | None) -> datetime | None:
    if (m := _DATE_RE.search(body or "")):
        try:
            month, day, year = re.split(r"[ ,]+", m.group("d").strip())
            return datetime(int(year), _MONTHS[month.lower()], int(day), tzinfo=timezone.utc)
        except (ValueError, KeyError):
            pass
    return fallback


def _is_heading(line: str) -> bool:
    return 0 < len(line) < 70 and not line.rstrip().endswith((".", "!", "?", ":"))


def _slice(lines: list[str], start_kw: str, end_kws: tuple[str, ...]) -> list[str]:
    out: list[str] = []
    capturing = False
    for l in lines:
        if not capturing:
            if l.strip().lower() == start_kw.lower():
                capturing = True
            continue
        if any(e.lower() in l.lower() for e in end_kws):
            break
        out.append(l)
    return out


def _parse_summary(lines: list[str]) -> tuple[str, list[dict]]:
    intro, sections, cur = "", [], None
    for l in (x for x in lines if x.strip()):
        if _is_heading(l):
            cur = {"heading": l, "text": ""}
            sections.append(cur)
        elif cur is None:
            intro = (intro + " " + l).strip()
        else:
            cur["text"] = (cur["text"] + " " + l).strip()
    return intro, sections


def _parse_steps(lines: list[str]) -> list[dict]:
    items: list[dict] = []
    for l in lines:
        if (m := _STEP_RE.match(l)):
            items.append({
                "owner": (m.group("owner") or "").strip(),
                "title": m.group("title").strip(),
                "detail": m.group("detail").strip(),
            })
    return items


def parse_gemini_email(subject: str, body: str, received: datetime | None = None) -> dict:
    """Parse a Gemini 'meeting notes' email into a recap dict."""
    lines = _lines(body)
    intro, sections = _parse_summary(_slice(lines, "Summary", ("Suggested next steps",)))
    actions = _parse_steps(_slice(lines, "Suggested next steps", _END_MARKERS))
    owners = [a["owner"] for a in actions if a["owner"] and a["owner"].lower() != "the group"]
    return {
        "external_id": None,
        "title": _extract_title(subject, body),
        "meeting_date": _extract_date(body, received),
        "summary": intro,
        "sections": sections,
        "action_items": actions,
        "attendees": list(dict.fromkeys(owners)),
        "source": "gemini",
    }


def html_to_text(html: str) -> str:
    """Very small HTML→text: drop tags, decode a few entities, keep line breaks.
    Enough to parse Gemini's markers and `[Owner] Title: detail` list items."""
    import html as _html

    text = re.sub(r"(?i)</(p|div|tr|li|h[1-6]|table|ul|ol|br)\s*>", "\n", html)
    text = re.sub(r"(?i)<br\s*/?>", "\n", text)
    text = re.sub(r"(?s)<(script|style).*?</\1>", "", text)
    text = re.sub(r"<[^>]+>", "", text)
    text = _html.unescape(text)
    return re.sub(r"[ \t]+\n", "\n", text)


# A real Gemini recap (used as the offline mock + to validate the parser).
SAMPLE_EMAIL = """Notes from 'Development check in'
These notes have been sent to Invited guests in your organisation.
Open meeting notes
The content was auto-generated on July 22, 2026, 12:34 PM CEST, and may contain errors.
Summary
Meeting participants refined user interface settings, consolidated single sign on configurations, and finalized tracking for analytics.
Single Sign On Consolidation
Consensus was reached to proceed with a single sign on setup supporting language variants. This approach simplifies customer management compared to maintaining multiple independent connection definitions.
Translation and Artificial Intelligence
Translation efforts focused on per-object navigation rather than monolithic pages for improved usability. The initial artificial intelligence pilot program reached a conclusion, allowing limited feature access.
Analytics Implementation Strategy
Analytics strategy prioritized tracking basic feature adoption through specific events rather than broad, undefined data collection. This methodology balances technical efficiency with necessary insights into user behavior.
Suggested next steps
\t[Bogdan Lazar] Update Mockups: Revise mockups to clearly indicate user location within settings. Improve navigation clarity between user and organization profiles.
\t[The group] Create Template: Develop new verification email template to allow customization. Ensure the template supports all required verification flows.
\t[Et'hem Kalaja] Test Connection: Test and establish connection with authentic for single sign on testing purposes. Utilize existing setup to verify single sign on configurations.
\t[The group] Fix Profile: Correct the missing user profile fields on the new settings page. Ensure all necessary profile data is visible to users.
\t[Et'hem Kalaja] Test Organizations: Verify the functionality of the organization settings page. Confirm that the page displays correctly.
\t[Bogdan Lazar] Integrate public key: Add public key reference to integration process to facilitate identification.
\t[Matous Hora] Implement AI permissions: Add AI assistant use and AI assistant manage permissions to guard front end user interface and tools.
\t[Freddie Robinson] Connect backend data: Link translation editor to real backend data to remove hardcoded JSON samples.
\t[The group] Define Tracking List: Create a list of 20 simple events to track, including navigations and dashboard activities.
We've updated the Decisions section based on your feedback.
What do you think?
Meeting records Document Notes by Gemini
"""


class GeminiRecapService(ABC):
    @abstractmethod
    def account_label(self) -> str: ...

    @abstractmethod
    def fetch_recaps(self) -> list[dict]:
        """Recaps newest-first, each a dict shaped like `parse_gemini_email`."""


class MockGeminiRecapService(GeminiRecapService):
    def account_label(self) -> str:
        return "Gemini (sample)"

    def fetch_recaps(self) -> list[dict]:
        rec = parse_gemini_email(
            "Notes: 'Development check in'",
            SAMPLE_EMAIL,
            datetime(2026, 7, 22, 12, 34, tzinfo=timezone.utc),
        )
        rec["external_id"] = "sample-development-check-in-2026-07-22"
        return [rec]


class LiveGeminiRecapService(GeminiRecapService):
    """Pull Gemini notes emails over IMAP and parse them."""

    def account_label(self) -> str:
        from app.config import settings

        return f"Gemini · {settings.mail_address}"

    def fetch_recaps(self) -> list[dict]:
        import email
        import imaplib
        from email.header import decode_header
        from email.utils import parsedate_to_datetime

        from app.config import settings

        def _decode(raw: str) -> str:
            parts = decode_header(raw or "")
            return "".join(
                p.decode(enc or "utf-8", "ignore") if isinstance(p, bytes) else p
                for p, enc in parts
            )

        def _body(msg) -> str:
            html = plain = ""
            for part in msg.walk() if msg.is_multipart() else [msg]:
                ctype = part.get_content_type()
                if part.get("Content-Disposition"):
                    continue
                try:
                    payload = part.get_payload(decode=True) or b""
                    chunk = payload.decode(part.get_content_charset() or "utf-8", "ignore")
                except Exception:
                    continue
                if ctype == "text/plain":
                    plain += chunk
                elif ctype == "text/html":
                    html += chunk
            return plain if plain.strip() else html_to_text(html)

        recaps: list[dict] = []
        try:
            box = imaplib.IMAP4_SSL(settings.mail_imap_host)
            box.login(settings.mail_address, settings.mail_app_password)
            box.select("INBOX")
            typ, data = box.search(None, "FROM", f'"{GEMINI_SENDER}"')
            ids = data[0].split()[-settings.mail_sync_limit:]
            for num in reversed(ids):
                typ, msg_data = box.fetch(num, "(RFC822)")
                if not msg_data or not msg_data[0]:
                    continue
                msg = email.message_from_bytes(msg_data[0][1])
                received = None
                try:
                    received = parsedate_to_datetime(msg.get("Date"))
                except (TypeError, ValueError):
                    pass
                rec = parse_gemini_email(_decode(msg.get("Subject", "")), _body(msg), received)
                rec["external_id"] = msg.get("Message-ID") or f"{rec['title']}-{rec['meeting_date']}"
                if rec["action_items"] or rec["summary"]:
                    recaps.append(rec)
            box.logout()
        except Exception:
            return recaps
        return recaps


def _parse_iso(value) -> datetime | None:
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    except ValueError:
        return None


class AppsScriptRecapService(GeminiRecapService):
    """Pull Gemini recaps from a Google Apps Script web app (its doGet returns
    JSON). Cadence GETs the stable /exec URL — no inbound public URL needed."""

    def account_label(self) -> str:
        return "Gemini · Apps Script"

    def fetch_recaps(self) -> list[dict]:
        from app.config import settings

        url = settings.recaps_script_url
        if not url:
            return []
        params = {"token": settings.recaps_webhook_secret} if settings.recaps_webhook_secret else {}
        try:
            resp = httpx.get(url, params=params, timeout=45.0, follow_redirects=True)
            resp.raise_for_status()
            data = resp.json()
        except Exception:
            return []
        out: list[dict] = []
        for item in (data.get("recaps", []) if isinstance(data, dict) else []):
            rec = parse_gemini_email(
                item.get("subject", ""), item.get("body", ""), _parse_iso(item.get("date"))
            )
            rec["external_id"] = item.get("id") or rec.get("external_id")
            if rec["action_items"] or rec["summary"]:
                out.append(rec)
        return out


def get_gemini_recap_service() -> GeminiRecapService:
    """Pull from the Apps Script web app if configured, else IMAP if a mailbox is
    set, else the offline mock."""
    from app.config import settings

    if settings.recaps_script_url:
        return AppsScriptRecapService()
    if settings.mail_address and settings.mail_app_password:
        return LiveGeminiRecapService()
    return MockGeminiRecapService()
