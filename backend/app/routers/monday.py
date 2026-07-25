"""monday.com endpoints: connect (mock or live), list boards/items, sync,
disconnect, and import a monday item into risr/crm as a real ticket."""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models.enums import IssueType, Space, Status
from app.models.issue import Issue
from app.models.member import TeamMember
from app.models.monday import MondayAccount, MondayBoard, MondayItem
from app.models.sprint import Sprint
from app.routers.issues import _audit, _current_actor, _next_issue_key, _next_task_id
from app.schemas.monday import (
    MondayAccountOut,
    MondayBoardOut,
    MondayColumn,
    MondayConnectResult,
    MondayGroup,
    MondayImportResult,
    MondayItemOut,
    MondayOut,
    MondayOwner,
)
from app.services import monday_sync
from app.services.monday_service import MondayService, get_monday_service

router = APIRouter(prefix="/api/monday", tags=["monday"])

# monday priority label -> risr/crm priority int (0..3)
_PRIORITY_MAP: dict[str, int] = {
    "low": 0, "medium": 1, "med": 1, "normal": 1,
    "high": 2, "critical": 3, "urgent": 3,
}
# Column titles consumed into native ticket fields (or the description body) — not
# repeated in the "Details" list.
_NATIVE_COLS = {
    "status", "owner", "owners", "people", "person", "priority",
    "notes", "note", "description", "long text", "details", "text", "update", "updates",
}
# Column titles (lowercased) whose text becomes the ticket's description narrative.
_NOTES_KEYS = ("notes", "note", "description", "long text", "details", "update", "updates", "text")

# monday status label -> (risr/crm status, blocked)
_STATUS_MAP: dict[str, tuple[Status, bool]] = {
    "Working on it": (Status.inprogress, False),
    "In Progress": (Status.inprogress, False),
    "In Review": (Status.review, False),
    "Done": (Status.done, False),
    "Stuck": (Status.todo, True),
    "Blocked": (Status.todo, True),
    "On Hold": (Status.todo, True),
    "Not Started": (Status.todo, False),
    "Waiting": (Status.todo, False),
    "Backlog": (Status.backlog, False),
}


def _map_status(label: str | None) -> tuple[Status, bool]:
    """monday status label -> (risr/crm status, blocked). Case-insensitive; a
    'Backlog' label (or any unmapped/empty one) resolves to the backlog."""
    if not label:
        return (Status.backlog, False)
    if label in _STATUS_MAP:
        return _STATUS_MAP[label]
    low = label.strip().lower()
    for known, mapped in _STATUS_MAP.items():
        if known.lower() == low:
            return mapped
    return (Status.backlog, False)


def _account(db: Session) -> MondayAccount:
    acc = db.scalars(select(MondayAccount)).first()
    if acc is None:
        acc = MondayAccount(connected=False)
        db.add(acc)
        db.commit()
        db.refresh(acc)
    return acc


def _item_out(item: MondayItem) -> MondayItemOut:
    owner = None
    if item.owner_name:
        owner = MondayOwner(
            name=item.owner_name,
            initials=item.owner_initials or "",
            color=item.owner_color or "#95948b",
        )
    return MondayItemOut(
        id=item.id,
        item_id=item.item_id,
        name=item.name,
        group=item.group_title,
        status_label=item.status_label,
        status_color=item.status_color,
        owner=owner,
        url=item.url,
        updated_at=item.updated_at,
        columns=[MondayColumn(title=c.get("title", ""), value=c.get("text", "")) for c in (item.columns or [])],
        issue_key=item.issue_key,
        imported=item.issue_key is not None,
    )


def _board_out(board: MondayBoard) -> MondayBoardOut:
    return MondayBoardOut(
        id=board.id,
        board_id=board.board_id,
        name=board.name,
        description=board.description,
        kind=board.kind,
        url=board.url,
        groups=[MondayGroup(id=g["id"], title=g.get("title") or "") for g in (board.groups or []) if g.get("id")],
        item_count=len(board.items),
        items=[_item_out(i) for i in board.items],
    )


def _reconcile_links(db: Session, boards: list[MondayBoard]) -> None:
    """Clear soft links whose risr/crm issue was deleted, so an item stops
    claiming it's imported once its ticket is gone (and becomes importable again)."""
    linked = [i for b in boards for i in b.items if i.issue_key]
    if not linked:
        return
    keys = {i.issue_key for i in linked}
    existing = set(db.scalars(select(Issue.key).where(Issue.key.in_(keys))))
    changed = False
    for item in linked:
        if item.issue_key not in existing:
            item.issue_key = None
            changed = True
    if changed:
        db.commit()


@router.get("", response_model=MondayOut)
def get_monday(db: Session = Depends(get_db)) -> MondayOut:
    acc = _account(db)
    boards: list[MondayBoard] = []
    if acc.connected:
        boards = list(db.scalars(select(MondayBoard).order_by(MondayBoard.id)))
        _reconcile_links(db, boards)
    return MondayOut(
        account=MondayAccountOut.model_validate(acc),
        boards=[_board_out(b) for b in boards],
    )


@router.post("/connect", response_model=MondayConnectResult)
def connect(
    db: Session = Depends(get_db),
    monday: MondayService = Depends(get_monday_service),
) -> MondayConnectResult:
    acc = _account(db)
    boards, items = monday.import_boards(db)
    acc.connected = True
    acc.account_name = monday.account_name()
    acc.connected_at = datetime.now(timezone.utc)
    db.commit()
    imported = _auto_import(db)  # every item becomes a risr/crm ticket automatically
    db.refresh(acc)
    return MondayConnectResult(
        account=MondayAccountOut.model_validate(acc), boards=boards, items=items, imported=imported
    )


@router.post("/sync", response_model=MondayConnectResult)
def sync(
    db: Session = Depends(get_db),
    monday: MondayService = Depends(get_monday_service),
) -> MondayConnectResult:
    """Two-way Sync: pull monday changes into linked tickets, create tickets for
    new monday items, then push any locally-pending changes back to monday."""
    acc = _account(db)
    if not acc.connected:
        raise HTTPException(status_code=409, detail="monday.com is not connected")
    boards, items = monday.import_boards(db)
    db.commit()
    pulled = _pull_updates(db)          # monday → existing linked tickets (monday wins)
    created = _auto_import(db)          # new monday items → new tickets
    pushed = _push_pending(db)          # local/pending tickets → monday
    _reconcile_deleted(db)             # unlink tickets whose monday item vanished
    return MondayConnectResult(
        account=MondayAccountOut.model_validate(acc),
        boards=boards, items=items, imported=created, pulled=pulled, pushed=pushed,
    )


@router.post("/disconnect", response_model=MondayAccountOut)
def disconnect(db: Session = Depends(get_db)) -> MondayAccountOut:
    acc = _account(db)
    acc.connected = False
    db.commit()
    db.refresh(acc)
    return MondayAccountOut.model_validate(acc)


def _priority_from_columns(columns: list[dict] | None) -> int | None:
    """Map a monday Priority column value onto the risr/crm 0..3 priority scale.
    Tolerates decorated labels (e.g. "Critical ⚠️") by matching a known keyword."""
    for c in columns or []:
        if "priorit" in (c.get("title") or "").lower():
            text = (c.get("text") or "").strip().lower()
            if not text:
                return None
            if text in _PRIORITY_MAP:
                return _PRIORITY_MAP[text]
            return next((v for k, v in _PRIORITY_MAP.items() if k in text), None)
    return None


def _item_description(item: MondayItem, board_name: str) -> str:
    """The ticket description = the item's notes/long-text (its narrative). Every
    other monday field is shown verbatim in the structured `monday_fields` section
    (see `_item_out`/IssueDetail), so it's no longer dumped into the description."""
    cols = {(c.get("title") or "").strip().lower(): (c.get("text") or "").strip() for c in (item.columns or [])}
    notes = next((cols[k] for k in _NOTES_KEYS if cols.get(k)), "")
    return notes if notes else f"Imported from the monday.com board “{board_name}”."


def _ticket_from_item(
    db: Session, item: MondayItem, board: MondayBoard | None, actor: str | None
) -> str:
    """Create a risr/crm ticket mirroring a monday item; link it back and audit.
    The ticket's Product is set to the board name so it's categorised (sidebar
    sections + category pages) exactly the way monday groups it into boards."""
    status, blocked = _map_status(item.status_label)
    # Only adopt the owner as assignee if it maps to a real risr/crm member.
    assignee = item.owner_initials if item.owner_initials and db.get(TeamMember, item.owner_initials) else None
    priority = _priority_from_columns(item.columns)
    board_name = board.name if board else "monday.com"
    # Route by status: a Backlog item is unscheduled (it belongs in the Backlog, not
    # the sprint board); any other status lands in the active sprint so it shows on
    # the (sprint-filtered) Board.
    active = db.scalars(select(Sprint).where(Sprint.active.is_(True))).first()
    sprint_id = None if status == Status.backlog else (active.id if active else None)
    key = _next_issue_key(db, Space.features)
    issue = Issue(
        key=key,
        type=IssueType.task,
        title=item.name,
        description=_item_description(item, board_name),
        task_id=_next_task_id(db),
        status=status,
        priority=priority if priority is not None else 1,
        space=Space.features,
        blocked=blocked,
        assignee_initials=assignee,
        product=board_name,
        sprint_id=sprint_id,
        labels=["monday"],
        comment_count=0,
        # Keep monday's real status label/colour + every field verbatim.
        monday_status=item.status_label,
        monday_status_color=item.status_color,
        monday_fields=item.columns or [],
        # Reverse link so monday-origin tickets aren't seen as push-pending.
        monday_item_id=item.item_id,
        monday_board_id=(board.board_id if board else None),
        monday_synced_at=datetime.now(timezone.utc),
    )
    db.add(issue)
    db.flush()
    item.issue_key = key
    _audit(db, key, actor, f"imported from monday.com board “{board_name}”")
    return key


def _auto_import(db: Session) -> int:
    """Create a risr/crm ticket for every monday item that doesn't already have a
    live one. Idempotent — items whose linked ticket still exists are skipped."""
    items = list(db.scalars(select(MondayItem).order_by(MondayItem.board_pk, MondayItem.position)))
    boards = {b.id: b for b in db.scalars(select(MondayBoard))}
    linked = {i.issue_key for i in items if i.issue_key}
    alive = set(db.scalars(select(Issue.key).where(Issue.key.in_(linked)))) if linked else set()
    actor = _current_actor(db)
    created = 0
    for item in items:
        if item.issue_key and item.issue_key in alive:
            continue
        _ticket_from_item(db, item, boards.get(item.board_pk), actor)
        created += 1
    if created:
        db.commit()
    return created


def _apply_monday_to_issue(db: Session, issue: Issue, item: MondayItem, board_name: str) -> bool:
    """Overwrite a linked ticket's SHARED fields from monday (monday wins), only
    where they differ. risr/crm-only fields (points/epic/PR/AI/audit) untouched;
    sprint placement follows the status so a Backlog item lands in the Backlog."""
    changed = False
    status, blocked = _map_status(item.status_label)
    if item.status_label and issue.status != status:
        issue.status = status
        changed = True
        # Keep board/backlog placement in step with the monday status: a Backlog
        # status parks the ticket in the Backlog (unscheduled); any other status
        # returns it to the active sprint so it appears on the board.
        if status == Status.backlog:
            issue.sprint_id = None
        elif issue.sprint_id is None:
            active = db.scalars(select(Sprint).where(Sprint.active.is_(True))).first()
            issue.sprint_id = active.id if active else None
    if item.status_label and issue.blocked != blocked:
        issue.blocked = blocked
        changed = True
    # Keep the raw monday status label/colour (this changes even when two monday
    # statuses collapse to the same risr/crm status, e.g. Not Started ↔ Stuck).
    if item.status_label and issue.monday_status != item.status_label:
        issue.monday_status = item.status_label
        issue.monday_status_color = item.status_color
        changed = True
    # Keep every monday field verbatim.
    if (item.columns or []) != (issue.monday_fields or []):
        issue.monday_fields = item.columns or []
        changed = True
    prio = _priority_from_columns(item.columns)
    if prio is not None and issue.priority != prio:
        issue.priority = prio
        changed = True
    if item.name and issue.title != item.name:
        issue.title = item.name
        changed = True
    desc = _item_description(item, board_name)
    if desc != issue.description:
        issue.description = desc
        changed = True
    if board_name and issue.product != board_name:
        issue.product = board_name
        changed = True
    if changed:
        issue.monday_synced_at = datetime.now(timezone.utc)
    return changed


def _pull_updates(db: Session) -> int:
    """monday → risr/crm: update every linked ticket from its monday item."""
    items = list(db.scalars(select(MondayItem).where(MondayItem.issue_key.is_not(None))))
    boards = {b.id: b for b in db.scalars(select(MondayBoard))}
    updated = 0
    touched = False
    for item in items:
        issue = db.get(Issue, item.issue_key)
        if issue is None:
            continue
        board = boards.get(item.board_pk)
        # Backfill the reverse link for tickets imported before it existed.
        if issue.monday_item_id != item.item_id:
            issue.monday_item_id = item.item_id
            issue.monday_board_id = board.board_id if board else None
            touched = True
        if _apply_monday_to_issue(db, issue, item, board.name if board else "monday.com"):
            updated += 1
            touched = True
        # A linked ticket is in sync with monday right after a pull — stamp it so
        # push-pending doesn't needlessly re-push imported values back to monday.
        if issue.monday_synced_at is None:
            issue.monday_synced_at = datetime.now(timezone.utc)
            touched = True
    if touched:
        db.commit()
    return updated


def _push_pending(db: Session) -> int:
    """risr/crm → monday: re-push dirty linked tickets, and create for unlinked
    tickets when a single target board is unambiguous (best-effort backfill)."""
    pushed = 0
    dirty = list(
        db.scalars(
            select(Issue).where(Issue.monday_item_id.is_not(None), Issue.monday_synced_at.is_(None))
        )
    )
    for issue in dirty:
        monday_sync.push_patch(db, issue, monday_sync.SHARED_FIELDS)
        if issue.monday_synced_at is not None:
            pushed += 1
    board = monday_sync.resolve_board(db)  # sole board, else None
    if board is not None:
        unlinked = list(
            db.scalars(
                select(Issue).where(Issue.monday_item_id.is_(None), Issue.type != IssueType.epic)
            )
        )
        for issue in unlinked:
            monday_sync.push_create(db, issue, board.board_id, None)
            if issue.monday_item_id:
                pushed += 1
    return pushed


def _reconcile_deleted(db: Session) -> None:
    """A ticket whose linked monday item no longer exists → unlink it + audit
    (we keep the risr/crm ticket; deletes only propagate risr/crm → monday)."""
    live = set(db.scalars(select(MondayItem.item_id)))
    orphaned = list(db.scalars(select(Issue).where(Issue.monday_item_id.is_not(None))))
    changed = False
    for issue in orphaned:
        if issue.monday_item_id not in live:
            issue.monday_item_id = None
            issue.monday_board_id = None
            _audit(db, issue.key, _current_actor(db), "monday item was deleted")
            changed = True
    if changed:
        db.commit()


@router.post("/items/{item_id}/import", response_model=MondayImportResult)
def import_item(item_id: int, db: Session = Depends(get_db)) -> MondayImportResult:
    """Create a real risr/crm ticket from a single monday item (idempotent per item).
    Kept for manual re-import; connect/refresh import everything automatically."""
    item = db.get(MondayItem, item_id)
    if item is None:
        raise HTTPException(status_code=404, detail="monday item not found")

    # Already imported (and the ticket still exists) → return it unchanged.
    if item.issue_key and db.get(Issue, item.issue_key):
        return MondayImportResult(item=_item_out(item), issue_key=item.issue_key)

    board = db.get(MondayBoard, item.board_pk)
    key = _ticket_from_item(db, item, board, _current_actor(db))
    db.commit()
    db.refresh(item)
    return MondayImportResult(item=_item_out(item), issue_key=key)
