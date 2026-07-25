"""Ybug feedback behind an interface.

`build_issue_fields()` maps a Ybug feedback payload (the shape Ybug POSTs to the
webhook / returns from its REST API) onto Cadence ticket fields. `YbugService` is
the poll seam: `MockYbugService` returns simulated feedback so the flow is demoable
offline; `LiveYbugService` hits the Ybug REST API when an API key is configured.
Real-time still flows through the webhook (routers/ybug.py) regardless.
"""
from __future__ import annotations

import re
from abc import ABC, abstractmethod

_PRIORITY = {"low": 0, "medium": 1, "normal": 1, "high": 2, "urgent": 3, "critical": 3}
_TYPE_WORDS = {
    "bug": "bug", "defect": "bug", "issue": "bug", "error": "bug",
    "task": "task", "chore": "task", "improvement": "task", "suggestion": "task",
    "story": "story", "feature": "story", "request": "story",
}


def _has(name: str, *needles: str) -> bool:
    low = name.lower()
    return any(n in low for n in needles)


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:24]


def _custom_fields(fb: dict) -> list[tuple[str, str]]:
    """Best-effort (label, value) pairs from Ybug custom fields / custom data.
    Ybug's exact payload key isn't documented, so scan the common shapes."""
    pairs: list[tuple[str, str]] = []
    seen: set[str] = set()

    def add(label: object, value: object) -> None:
        name = str(label or "").strip()
        if isinstance(value, (list, tuple)):
            value = ", ".join(str(v) for v in value if v not in (None, ""))
        text = str("" if value is None else value).strip()
        key = name.lower()
        if name and text and key not in seen:
            seen.add(key)
            pairs.append((name, text))

    attrs = fb.get("attributes") or {}
    sources = [
        fb.get("custom_data"), fb.get("customData"), fb.get("custom_fields"),
        fb.get("customFields"), fb.get("custom"), fb.get("fields"),
        attrs.get("custom_data"), attrs.get("customData"),
    ]
    for src in sources:
        if isinstance(src, dict):
            for k, v in src.items():
                if isinstance(v, dict) and ("value" in v or "label" in v):
                    add(v.get("label") or k, v.get("value"))
                else:
                    add(k, v)
        elif isinstance(src, list):
            for item in src:
                if isinstance(item, dict):
                    add(
                        item.get("label") or item.get("name") or item.get("title") or item.get("key"),
                        item.get("value") if item.get("value") is not None else item.get("text"),
                    )
    return pairs


def build_issue_fields(fb: dict) -> dict:
    """Ybug feedback → Issue kwargs (type, title, priority, description)."""
    attrs = fb.get("attributes") or {}
    reporter = fb.get("reporter") or {}
    comment = (fb.get("comment") or "").strip()
    title = (fb.get("title") or "").strip() or (
        comment.splitlines()[0][:120] if comment else "Ybug feedback"
    )
    tname = (fb.get("type") or {}).get("name", "") if isinstance(fb.get("type"), dict) else ""
    issue_type = "bug" if ("bug" in tname.lower() or not tname) else "task"
    pname = (fb.get("priority") or {}).get("name", "") if isinstance(fb.get("priority"), dict) else ""
    priority = _PRIORITY.get(pname.lower(), 1)

    # Custom fields from the feedback form (dashboard-configured) let reporters
    # categorize at capture time. Map recognised ones onto ticket fields, and
    # keep every field (as a label + in the description) so nothing is lost.
    custom = _custom_fields(fb)
    space = "features"
    labels: list[str] = []
    for name, value in custom:
        low = value.lower()
        if _has(name, "sever", "priorit", "urgen") and low in _PRIORITY:
            priority = _PRIORITY[low]
        elif _has(name, "type", "kind") and low in _TYPE_WORDS:
            issue_type = _TYPE_WORDS[low]
        elif _has(name, "space", "board", "queue") and low in ("support", "help", "helpdesk"):
            space = "support"
        if len(value) <= 24 and "\n" not in value:
            labels.append(_slug(value))

    lines: list[str] = []
    if comment:
        lines += [comment, ""]
    lines.append("## Feedback details")
    who = reporter.get("name") or reporter.get("email") or "Anonymous"
    email = f" ({reporter['email']})" if reporter.get("email") else ""
    lines.append(f"- Reporter: {who}{email}")
    page = fb.get("url") or attrs.get("location")
    if page:
        lines.append(f"- Page: {page}")
    browser = " ".join(x for x in [attrs.get("browser"), str(attrs.get("browserVersion") or "")] if x).strip()
    plat = " ".join(x for x in [attrs.get("platform"), str(attrs.get("platformVersion") or "")] if x).strip()
    if browser:
        lines.append(f"- Browser: {browser}")
    if plat:
        lines.append(f"- OS: {plat}")
    if attrs.get("deviceType"):
        lines.append(f"- Device: {attrs['deviceType']}")
    if custom:
        lines += ["", "## Reported categories"]
        lines += [f"- {name}: {value}" for name, value in custom]
    # Screenshot renders inline as a clickable image; report/video as links.
    shot = fb.get("screenshotUrl") or fb.get("screenshot_url") or fb.get("screenshot")
    if isinstance(shot, dict):
        shot = shot.get("url")
    if shot:
        lines += ["", "## Screenshot", f"![Screenshot]({shot})"]
    for label, keys in (("Open full report", ("reportUrl", "report_url")),
                        ("Watch video", ("videoUrl", "video_url"))):
        val = next((fb[k] for k in keys if fb.get(k)), None)
        if val:
            lines += ["", f"[{label}]({val})"]
    console = attrs.get("consoleLog")
    if console:
        text = console if isinstance(console, str) else "\n".join(str(c) for c in console[:8])
        if text.strip():
            lines += ["", "## Console log", text[:1500]]
    return {
        "type": issue_type,
        "title": title[:200],
        "priority": priority,
        "space": space,
        "labels": list(dict.fromkeys(labels)),
        "description": "\n".join(lines),
    }


# Deterministic demo feedback (shaped like Ybug's real payload).
_SAMPLES = [
    {
        "title": "Submit button overlaps footer on mobile",
        "comment": "On the pricing page the “Get started” button overlaps the footer on my phone and I can't tap it.",
        "type": {"name": "Bug"}, "priority": {"name": "High"},
        "url": "https://acme.example/pricing", "browser": "Safari", "platform": "iOS", "device": "mobile",
        "reporter": {"name": "Dana Cole", "email": "dana@brightpath.co"},
    },
    {
        "title": "Typo in onboarding copy",
        "comment": "“Welcom” should be “Welcome” on the first onboarding step.",
        "type": {"name": "Suggestion"}, "priority": {"name": "Low"},
        "url": "https://acme.example/onboarding", "browser": "Chrome", "platform": "macOS", "device": "desktop",
        "reporter": {"name": "Marcus Webb", "email": "marcus@globex.io"},
    },
]


def sample_feedback(fid: str, i: int = 0) -> dict:
    s = _SAMPLES[i % len(_SAMPLES)]
    return {
        "id": fid,
        "title": s["title"],
        "comment": s["comment"],
        "type": s["type"],
        "priority": s["priority"],
        "url": s["url"],
        "reporter": s["reporter"],
        "attributes": {
            "browser": s["browser"], "browserVersion": "17.0",
            "platform": s["platform"], "platformVersion": "",
            "deviceType": s["device"], "location": s["url"],
            "consoleLog": "[error] TypeError: Cannot read properties of undefined (reading 'id')",
        },
        "screenshotUrl": f"https://ybug.io/s/{fid}.png",
        "reportUrl": f"https://ybug.io/r/{fid}",
    }


class YbugService(ABC):
    @abstractmethod
    def account_name(self) -> str: ...

    @abstractmethod
    def fetch_new(self, since_id: str | None) -> list[dict]:
        """Feedback items newer than `since_id` (for the poll/Sync flow)."""


class MockYbugService(YbugService):
    def account_name(self) -> str:
        return "Ybug · Acme (demo)"

    def fetch_new(self, since_id: str | None) -> list[dict]:
        items = [sample_feedback("1001", 0), sample_feedback("1002", 1)]
        if since_id:
            items = [f for f in items if str(f["id"]) > str(since_id)]
        return items


_mock_service: YbugService = MockYbugService()
_live_service: YbugService | None = None


def get_ybug_service() -> YbugService:
    """Live Ybug REST poll when an API key is configured (`CADENCE_YBUG_API_KEY`),
    otherwise the offline mock. (The webhook path works regardless of this.)"""
    from app.config import settings

    if settings.ybug_api_key:
        global _live_service
        if _live_service is None:
            from app.services.ybug_live import LiveYbugService

            _live_service = LiveYbugService()
        return _live_service
    return _mock_service
