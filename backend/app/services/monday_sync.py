"""Write-through sync: push Cadence issue create/edit/delete out to monday.com.

Best-effort and NON-BLOCKING — a monday failure never fails the Cadence request;
the issue is flagged pending (`monday_synced_at = NULL`) and re-pushed on the next
Sync. Kept out of routers/issues.py and routers/monday.py to avoid import cycles.

Loop-guard: these hooks fire ONLY from the create/patch/delete endpoints. The
pull side (routers/monday.py sync) mutates ORM fields directly and never calls
these, so a pulled value is never echoed back to monday.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.enums import Status
from app.models.issue import Issue
from app.models.monday import MondayAccount, MondayBoard, MondayItem
from app.services.monday_service import (
    STATUS_COLORS,
    build_column_values,
    get_monday_service,
)

log = logging.getLogger("cadence.monday_sync")

# Cadence → monday label CANDIDATES (ordered). Boards use different wording for
# the same concept (balh "In Progress" vs a default board's "Working on it"), so
# we offer synonyms and `_closest_label` picks whichever the board actually has.
_STATUS_SYNONYMS: dict[Status, list[str]] = {
    Status.inprogress: ["Working on it", "In Progress", "Doing", "Active", "WIP", "Started"],
    Status.review: ["In Review", "Review", "QA", "Reviewing"],
    Status.done: ["Done", "Complete", "Completed", "Closed", "Resolved"],
    Status.todo: ["Not Started", "To Do", "Todo", "Open", "New", "Backlog"],
    Status.backlog: ["Not Started", "Backlog", "To Do", "Open", "New"],
}
_BLOCKED_SYNONYMS = ["Stuck", "Blocked", "On Hold", "Waiting"]
_PRIORITY_SYNONYMS: dict[int, list[str]] = {
    0: ["Low"],
    1: ["Medium", "Normal", "Med"],
    2: ["High"],
    3: ["Urgent", "Critical", "Highest"],
}

# Issue fields that have a monday equivalent and should push when they change.
SHARED_FIELDS = {"status", "title", "priority", "blocked", "description"}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _connected(db: Session) -> bool:
    acc = db.scalars(select(MondayAccount)).first()
    return bool(acc and acc.connected)


def resolve_board(db: Session, board_id: str | None = None) -> MondayBoard | None:
    """The board to create into: the chosen one, else the sole connected board."""
    if board_id:
        return db.scalars(select(MondayBoard).where(MondayBoard.board_id == str(board_id))).first()
    boards = list(db.scalars(select(MondayBoard)))
    return boards[0] if len(boards) == 1 else None


def _status_candidates(issue: Issue) -> list[str]:
    """Ordered monday status-label candidates for a Cadence issue (blocked first)."""
    if issue.blocked:
        return _BLOCKED_SYNONYMS + _STATUS_SYNONYMS.get(issue.status, [])
    return _STATUS_SYNONYMS.get(issue.status, [])


def _status_label(issue: Issue) -> str | None:
    """First status candidate — used for the local MondayItem mirror display."""
    cands = _status_candidates(issue)
    return cands[0] if cands else None


def _notes_from_description(desc: str | None) -> str | None:
    """The description is `<notes>\\n\\n## Details\\n…`; push only the notes body."""
    if not desc:
        return None
    body = desc.split("## Details")[0].strip()
    return body or None


def _values_for(board: MondayBoard, issue: Issue) -> dict:
    return build_column_values(
        board,
        status_label=_status_candidates(issue),
        priority_label=_PRIORITY_SYNONYMS.get(issue.priority, []),
        notes=_notes_from_description(issue.description),
    )


def _mirror(db: Session, issue: Issue, board: MondayBoard, item_id: str, group_id: str | None) -> None:
    """Upsert the local MondayItem row for a Cadence-originated item so (a) the
    monday page shows it before the next pull and (b) the pull's link-preservation
    (by item_id) keeps it linked instead of re-importing a duplicate ticket."""
    item = db.scalars(select(MondayItem).where(MondayItem.item_id == item_id)).first()
    if item is None:
        item = MondayItem(board_pk=board.id, item_id=item_id, position=999)
        db.add(item)
    label = _status_label(issue)
    item.board_pk = board.id
    item.name = issue.title
    item.group_title = next(
        (g.get("title") for g in (board.groups or []) if g.get("id") == group_id), ""
    )
    item.status_label = label
    item.status_color = STATUS_COLORS.get(label or "", "#c4c4c4") if label else None
    item.url = f"{board.url}/pulses/{item_id}" if board.url else None
    item.issue_key = issue.key


def push_create(db: Session, issue: Issue, board_id: str | None = None, group_id: str | None = None) -> None:
    """Create a matching monday item for a new Cadence issue and link them."""
    if not _connected(db):
        return
    board = resolve_board(db, board_id)
    if board is None:
        return  # ambiguous target (multiple boards, none chosen) → Sync backfills
    group = group_id or (board.groups[0]["id"] if board.groups else None)
    if not group:
        return
    svc = get_monday_service()
    try:
        item_id = svc.create_item(board.board_id, group, issue.title, _values_for(board, issue))
    except Exception as exc:  # never fail the create
        log.warning("monday create failed for %s: %s", issue.key, exc)
        return
    if not item_id:
        return
    issue.monday_item_id = item_id
    issue.monday_board_id = board.board_id
    issue.monday_synced_at = _now()
    if not issue.product:
        issue.product = board.name
    _mirror(db, issue, board, item_id, group)
    db.commit()


def push_patch(db: Session, issue: Issue, changed: set[str]) -> None:
    """Push changed shared fields of a linked issue back to its monday item."""
    if not issue.monday_item_id or not _connected(db):
        return
    if not (changed & SHARED_FIELDS):
        return
    board = resolve_board(db, issue.monday_board_id)
    svc = get_monday_service()
    try:
        if board is not None:
            svc.change_columns(board.board_id, issue.monday_item_id, _values_for(board, issue))
        if "title" in changed:
            svc.rename_item(issue.monday_board_id or "", issue.monday_item_id, issue.title)
        issue.monday_synced_at = _now()
    except Exception as exc:
        log.warning("monday push failed for %s: %s", issue.key, exc)
        issue.monday_synced_at = None  # pending → retried on next Sync
    # Reflect the change on the local mirror so the monday page stays current.
    item = db.scalars(select(MondayItem).where(MondayItem.item_id == issue.monday_item_id)).first()
    if item is not None:
        label = _status_label(issue)
        item.name = issue.title
        item.status_label = label
        item.status_color = STATUS_COLORS.get(label or "", "#c4c4c4") if label else None
    db.commit()


def push_delete(db: Session, issue: Issue) -> None:
    """Delete the linked monday item (the caller then deletes the Cadence issue)."""
    if not issue.monday_item_id or not _connected(db):
        return
    svc = get_monday_service()
    try:
        svc.delete_item(issue.monday_item_id)
    except Exception as exc:
        log.warning("monday delete failed for %s: %s", issue.key, exc)
    # Drop the local mirror row (committed together with the issue delete).
    item = db.scalars(select(MondayItem).where(MondayItem.item_id == issue.monday_item_id)).first()
    if item is not None:
        db.delete(item)
