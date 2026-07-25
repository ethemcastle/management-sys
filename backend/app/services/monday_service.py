"""monday.com behind an interface.

`MondayService` is the seam; `MockMondayService` simulates a connected monday.com
account whose boards/items import into our tables. A real monday.com implementation
(`LiveMondayService`, GraphQL) swaps in via `get_monday_service()` when a personal
API token is configured — no API or frontend change.
"""
from __future__ import annotations

import uuid
from abc import ABC, abstractmethod
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.member import TeamMember
from app.models.monday import MondayBoard, MondayItem

# Authentic monday.com status colours, keyed by label (covers the common defaults
# plus a few frequent custom labels; unknown labels fall back to grey).
STATUS_COLORS: dict[str, str] = {
    "Working on it": "#fdab3d",
    "In Progress": "#fdab3d",
    "Done": "#00c875",
    "Stuck": "#e2445c",
    "Blocked": "#e2445c",
    "Not Started": "#c4c4c4",
    "In Review": "#a25ddc",
    "Waiting": "#784bd1",
    "On Hold": "#808080",
}

MOCK_ACCOUNT_NAME = "Acme Product Co"
_ACCOUNT_SLUG = "acme"

# Column definitions for the mock boards — mirrors what the live import captures
# from monday, so the New Ticket board/group picker and write-mapping work offline.
_MOCK_COLUMNS_META: list[dict] = [
    {"id": "status", "title": "Status", "type": "status",
     "labels": ["Not Started", "Working on it", "In Progress", "In Review", "Stuck", "Done"]},
    {"id": "priority", "title": "Priority", "type": "status",
     "labels": ["Low", "Medium", "High", "Critical"]},
    {"id": "person", "title": "Owner", "type": "people"},
    {"id": "notes", "title": "Notes", "type": "text"},
    {"id": "due", "title": "Due date", "type": "date"},
]

# Deterministic mock workspace: (board_id, name, description, kind, items)
# item = (name, group, status_label, owner_initials)
_MOCK_BOARDS: list[tuple[str, str, str, str, list[tuple[str, str, str, str | None]]]] = [
    (
        "7100001",
        "Product Roadmap",
        "Company-wide roadmap across Now / Next / Later.",
        "public",
        [
            ("Usage-based billing rollout", "Now", "Working on it", "MP"),
            ("Onboarding checklist revamp", "Now", "Working on it", "AR"),
            ("Enterprise SSO (Okta, SAML)", "Next", "Not Started", "JC"),
            ("Mobile app v2", "Next", "Not Started", "SL"),
            ("AI ticket triage", "Later", "Not Started", "AL"),
        ],
    ),
    (
        "7100002",
        "Bug Tracker",
        "Incoming bugs triaged by severity.",
        "public",
        [
            ("CSV export fails past 10k rows", "New", "Stuck", "MP"),
            ("Okta SSO login loop", "In Progress", "Working on it", "JC"),
            ("Calendar event off by one timezone", "In Progress", "Working on it", "AL"),
            ("Realtime drops on reconnect", "Resolved", "Done", "SL"),
        ],
    ),
    (
        "7100003",
        "Sprint 24",
        "Current sprint — engineering tasks.",
        "private",
        [
            ("Board WIP limits", "To Do", "Not Started", "AR"),
            ("Dark mode polish", "Doing", "Working on it", "AL"),
            ("Audit log CSV export", "Done", "Done", "JC"),
        ],
    ),
]


class MondayService(ABC):
    @abstractmethod
    def account_name(self) -> str: ...

    @abstractmethod
    def import_boards(self, db: Session) -> tuple[int, int]:
        """Import boards + items into our tables. Returns (boards, items)."""

    # --- write side (two-way sync). Mock simulates; live hits the GraphQL API. ---
    @abstractmethod
    def create_item(self, board_id: str, group_id: str, name: str, column_values: dict) -> str:
        """Create a monday item; return its item id."""

    @abstractmethod
    def change_columns(self, board_id: str, item_id: str, column_values: dict) -> None:
        """Set multiple column values on an existing item."""

    @abstractmethod
    def rename_item(self, board_id: str, item_id: str, name: str) -> None:
        """Rename an item (its Name/title)."""

    @abstractmethod
    def delete_item(self, item_id: str) -> None:
        """Delete an item from monday."""


class MockMondayService(MondayService):
    def account_name(self) -> str:
        return MOCK_ACCOUNT_NAME

    def import_boards(self, db: Session) -> tuple[int, int]:
        # Idempotent: if boards already exist, treat (re)connect/sync as a no-op —
        # preserves any items already imported into Cadence tickets.
        existing = db.scalar(select(func.count()).select_from(MondayBoard))
        if existing:
            items = db.scalar(select(func.count()).select_from(MondayItem)) or 0
            return existing, items

        members = {m.initials: m for m in db.scalars(select(TeamMember))}
        now = datetime.now(timezone.utc)
        boards = 0
        items = 0
        priorities = ["High", "Medium", "Low", "Critical"]
        for b_idx, (board_id, name, desc, kind, item_specs) in enumerate(_MOCK_BOARDS):
            board_url = f"https://{_ACCOUNT_SLUG}.monday.com/boards/{board_id}"
            # Distinct group titles (in order) become the board's groups.
            group_titles: list[str] = []
            for _n, g, _s, _o in item_specs:
                if g not in group_titles:
                    group_titles.append(g)
            board = MondayBoard(
                board_id=board_id, name=name, description=desc, kind=kind, url=board_url,
                columns_meta=[dict(c) for c in _MOCK_COLUMNS_META],
                groups=[{"id": f"g{gi}", "title": t} for gi, t in enumerate(group_titles)],
            )
            db.add(board)
            db.flush()  # get board.id for children
            boards += 1
            for i_idx, (item_name, group, status, owner_ini) in enumerate(item_specs):
                item_id = f"{board_id}{i_idx + 1:04d}"
                member = members.get(owner_ini) if owner_ini else None
                priority = priorities[(b_idx + i_idx) % len(priorities)]
                due = f"2026-07-{22 + ((b_idx + i_idx) % 7):02d}"
                # Full column snapshot (mirrors what the live import captures).
                columns = [
                    {"title": "Status", "text": status, "type": "status", "color": STATUS_COLORS.get(status)},
                    {"title": "Priority", "text": priority, "type": "status", "color": None},
                ]
                if member:
                    columns.append({"title": "Owner", "text": member.name, "type": "people"})
                columns.append({"title": "Due date", "text": due, "type": "date"})
                db.add(
                    MondayItem(
                        board_pk=board.id,
                        item_id=item_id,
                        name=item_name,
                        group_title=group,
                        status_label=status,
                        status_color=STATUS_COLORS.get(status),
                        owner_name=member.name if member else None,
                        owner_initials=owner_ini if member else None,
                        owner_color=member.color if member else None,
                        url=f"{board_url}/pulses/{item_id}",
                        updated_at=now - timedelta(hours=(b_idx * 5 + i_idx) * 3 + 2),
                        position=i_idx,
                        columns=columns,
                    )
                )
                items += 1
        db.flush()
        return boards, items

    # Mock write side: create returns a synthetic id; edits/deletes are no-ops
    # (the sync layer mirrors the change into the local MondayItem row so the
    # mock board still reflects it).
    def create_item(self, board_id: str, group_id: str, name: str, column_values: dict) -> str:
        return f"mock-{uuid.uuid4().hex[:10]}"

    def change_columns(self, board_id: str, item_id: str, column_values: dict) -> None:
        return None

    def rename_item(self, board_id: str, item_id: str, name: str) -> None:
        return None

    def delete_item(self, item_id: str) -> None:
        return None


# --- pure field-mapping helpers (Cadence field values -> monday column_values) ---
def _find_status_col(meta: list[dict]) -> dict | None:
    status_cols = [c for c in meta if c.get("type") == "status"]
    for c in status_cols:  # prefer a column literally titled "Status"
        if "status" in (c.get("title") or "").lower():
            return c
    for c in status_cols:  # else any status column that isn't the Priority one
        if "priorit" not in (c.get("title") or "").lower():
            return c
    return None


def _find_priority_col(meta: list[dict]) -> dict | None:
    for c in meta:
        if c.get("type") == "status" and "priorit" in (c.get("title") or "").lower():
            return c
    return None


def _find_notes_col(meta: list[dict]) -> dict | None:
    for c in meta:
        if c.get("type") == "text" and any(
            n in (c.get("title") or "").lower() for n in ("note", "description", "text")
        ):
            return c
    return None


def _closest_label(col: dict, wanted) -> str | None:
    """Resolve `wanted` (a label, or an ordered list of candidate labels) to a
    label that actually exists on the column, else None (monday rejects the whole
    mutation on an invalid label, so we skip instead). Matching is exact →
    case-insensitive → substring either-way, so 'In Progress' matches a board's
    'In progress' and 'Critical' matches 'Critical ⚠️'."""
    candidates = [wanted] if isinstance(wanted, str) else list(wanted or [])
    candidates = [c for c in candidates if c]
    if not candidates:
        return None
    labels = col.get("labels") or []
    if not labels:
        return candidates[0]  # unknown label set → best-effort first candidate
    lower = {lab.lower(): lab for lab in labels}
    for c in candidates:  # exact / case-insensitive
        if c.lower() in lower:
            return lower[c.lower()]
    for c in candidates:  # substring, either direction
        cl = c.lower()
        for lab in labels:
            ll = lab.lower()
            if cl in ll or ll in cl:
                return lab
    return None


def build_column_values(board, *, status_label=None, priority_label=None, notes=None) -> dict:
    """Build a monday `column_values` dict for a board from Cadence field values,
    targeting the right column ids and only sending labels the board actually has."""
    meta = getattr(board, "columns_meta", None) or []
    out: dict = {}
    st = _find_status_col(meta)
    if status_label and st and (lab := _closest_label(st, status_label)):
        out[st["id"]] = {"label": lab}
    pr = _find_priority_col(meta)
    if priority_label and pr and (lab := _closest_label(pr, priority_label)):
        out[pr["id"]] = {"label": lab}
    nt = _find_notes_col(meta)
    if notes is not None and nt:
        out[nt["id"]] = notes
    return out


_mock_service: MondayService = MockMondayService()
_live_service: MondayService | None = None


def get_monday_service() -> MondayService:
    """FastAPI dependency. Uses the live monday.com service when a personal API
    token is configured (`CADENCE_MONDAY_TOKEN`), otherwise the offline mock."""
    from app.config import settings

    if settings.monday_token:
        global _live_service
        if _live_service is None:
            from app.services.monday_live import LiveMondayService

            _live_service = LiveMondayService()
        return _live_service
    return _mock_service
