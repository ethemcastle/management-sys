"""Live monday.com implementation of `MondayService`.

Reads real boards and items from the monday.com GraphQL API (v2) and stores them
in the same tables the mock uses, so the frontend and import-as-ticket flow are
shared. Activated automatically when `CADENCE_MONDAY_TOKEN` is set (a personal API
token from monday.com → avatar → Developers → My access tokens). Dormant — and
falls back to the mock — until a token is present.

Status colours and owner colours from the API are best-effort: monday returns a
status *label* (mapped to the known palette, grey otherwise) and person *names*
(a colour is derived deterministically), which is all the UI needs.
"""
from __future__ import annotations

import html
import json
from datetime import datetime, timezone

import httpx
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.config import settings
from app.models.monday import MondayBoard, MondayItem
from app.services.monday_service import STATUS_COLORS, MockMondayService

_OWNER_PALETTE = ["#0E7C86", "#E8833A", "#2E9E5B", "#5A50E1", "#D95340", "#B45AF2", "#3B7DD8"]

_BOARDS_QUERY = """
query {
  boards (limit: 25, state: active, order_by: used_at) {
    id
    name
    description
    board_kind
    url
    groups { id title }
    columns { id title type settings_str }
    items_page (limit: 100) {
      items {
        id
        name
        group { id title }
        updated_at
        column_values {
          id
          type
          text
          column { title }
        }
      }
    }
  }
}
"""

_ACCOUNT_QUERY = "query { me { account { name } } }"


class MondayApiError(RuntimeError):
    """Raised when the monday.com API returns an error (auth, rate limit, query)."""

    def __init__(self, message: str, status: int | None = None):
        super().__init__(message)
        self.status = status


class LiveMondayService(MockMondayService):
    """Live board/item import; import-as-ticket + mock fallback are inherited."""

    def account_name(self) -> str:
        try:
            data = self._gql(_ACCOUNT_QUERY)
            name = (data.get("me") or {}).get("account", {}).get("name")
            if name:
                return name
        except MondayApiError:
            pass
        return super().account_name()

    def import_boards(self, db: Session) -> tuple[int, int]:
        """Replace the board/item pool with a fresh pull from monday.com,
        preserving import-as-ticket links (issue_key) by monday item id."""
        try:
            data = self._gql(_BOARDS_QUERY)
        except MondayApiError:
            # No/failed connection → keep whatever we have (or the mock seed).
            return super().import_boards(db)

        # Preserve soft links to risr/crm issues across a re-sync.
        links = {
            item_id: key
            for item_id, key in db.execute(
                select(MondayItem.item_id, MondayItem.issue_key).where(
                    MondayItem.issue_key.is_not(None)
                )
            )
        }

        db.execute(delete(MondayItem))
        db.execute(delete(MondayBoard))

        boards = 0
        items = 0
        for b in data.get("boards", []):
            # Skip monday's auto-generated subitem boards ("Subitems of X") — they
            # mirror another board's subitems and aren't real top-level boards.
            if (b.get("name") or "").startswith("Subitems of "):
                continue
            board_url = b.get("url") or f"https://monday.com/boards/{b['id']}"
            board = MondayBoard(
                board_id=str(b["id"]),
                name=b.get("name") or "Untitled board",
                description=b.get("description") or "",
                kind=b.get("board_kind") or "public",
                url=board_url,
                columns_meta=self._columns_meta(b.get("columns") or []),
                groups=[
                    {"id": g.get("id"), "title": g.get("title")}
                    for g in (b.get("groups") or [])
                    if g.get("id")
                ],
            )
            db.add(board)
            db.flush()
            boards += 1
            page = (b.get("items_page") or {}).get("items", [])
            for pos, it in enumerate(page):
                cols_raw = it.get("column_values") or []
                label, owner = self._extract(cols_raw)
                item_id = str(it["id"])
                name, color = owner
                db.add(
                    MondayItem(
                        board_pk=board.id,
                        item_id=item_id,
                        name=html.unescape(it.get("name") or "Untitled item"),
                        group_title=(it.get("group") or {}).get("title") or "",
                        status_label=label,
                        status_color=STATUS_COLORS.get(label or "", "#c4c4c4") if label else None,
                        owner_name=name,
                        owner_initials=self._initials(name) if name else None,
                        owner_color=color,
                        url=f"{board_url}/pulses/{item_id}",
                        updated_at=self._parse_dt(it.get("updated_at")),
                        position=pos,
                        columns=self._columns(cols_raw),
                        issue_key=links.get(item_id),
                    )
                )
                items += 1
        db.flush()
        return boards, items

    # --- helpers ------------------------------------------------------------
    def _extract(self, columns: list[dict]) -> tuple[str | None, tuple[str | None, str | None]]:
        """Pull a status label and the first owner (name, colour) from column values.

        A board can have several status/colour columns (e.g. Status *and* Priority),
        so we rank by the column's title — a column literally called "Status" wins,
        a "Priority" column loses — to avoid importing a priority value as the status.
        """
        status_candidates: list[tuple[int, str]] = []
        owner_name: str | None = None
        for c in columns:
            ctype = c.get("type")
            text = (c.get("text") or "").strip()
            if not text:
                continue
            title = ((c.get("column") or {}).get("title") or "").lower()
            if ctype in ("status", "color"):
                # rank 0 = a column titled "Status"; rank 1 = a generic colour column;
                # priority columns are excluded (a priority is not a status).
                if "priorit" in title:
                    continue
                status_candidates.append((0 if "status" in title else 1, text))
            elif ctype in ("people", "person", "multiple-person") and owner_name is None:
                owner_name = html.unescape(text.split(",")[0].strip())
        label = min(status_candidates)[1] if status_candidates else None
        color = None
        if owner_name:
            color = _OWNER_PALETTE[sum(map(ord, owner_name)) % len(_OWNER_PALETTE)]
        return label, (owner_name, color)

    def _columns(self, columns: list[dict]) -> list[dict]:
        """Every non-empty column on the item as {title, text, type, color?} — the
        full data snapshot, stored so EVERY monday field is readable verbatim inside
        risr/crm (status/priority carry a colour so they render as coloured pills)."""
        out: list[dict] = []
        for c in columns:
            text = (c.get("text") or "").strip()
            title = ((c.get("column") or {}).get("title") or "").strip()
            if not (text and title):
                continue
            ctype = c.get("type")
            field = {"title": html.unescape(title), "text": html.unescape(text), "type": ctype}
            if ctype in ("status", "color"):
                field["color"] = STATUS_COLORS.get(field["text"])
            out.append(field)
        return out

    def _columns_meta(self, columns: list[dict]) -> list[dict]:
        """Board-level column definitions needed to WRITE values back:
        {id, title, type, labels}. `labels` (the allowed status texts) is parsed
        from a status column's settings_str so we only send valid labels."""
        out: list[dict] = []
        for c in columns:
            meta = {"id": c.get("id"), "title": c.get("title"), "type": c.get("type")}
            if c.get("type") == "status":
                try:
                    labels = json.loads(c.get("settings_str") or "{}").get("labels", {})
                    meta["labels"] = [v for v in labels.values() if v]
                except (ValueError, TypeError):
                    meta["labels"] = []
            out.append(meta)
        return out

    def _initials(self, name: str) -> str:
        parts = [p for p in name.split() if p]
        if not parts:
            return "?"
        if len(parts) == 1:
            return parts[0][:2].upper()
        return (parts[0][0] + parts[-1][0]).upper()

    def _parse_dt(self, raw: str | None) -> datetime | None:
        if not raw:
            return None
        try:
            return datetime.fromisoformat(raw.replace("Z", "+00:00"))
        except ValueError:
            return None

    # --- write mutations (two-way sync) -------------------------------------
    def create_item(self, board_id: str, group_id: str, name: str, column_values: dict) -> str:
        q = """mutation ($board: ID!, $group: String!, $name: String!, $cols: JSON!) {
          create_item (board_id: $board, group_id: $group, item_name: $name, column_values: $cols) { id }
        }"""
        data = self._gql(
            q,
            {"board": str(board_id), "group": group_id, "name": name,
             "cols": json.dumps(column_values or {})},
        )
        return str((data.get("create_item") or {}).get("id") or "")

    def change_columns(self, board_id: str, item_id: str, column_values: dict) -> None:
        if not column_values:
            return
        q = """mutation ($board: ID!, $item: ID!, $cols: JSON!) {
          change_multiple_column_values (board_id: $board, item_id: $item, column_values: $cols) { id }
        }"""
        self._gql(q, {"board": str(board_id), "item": str(item_id), "cols": json.dumps(column_values)})

    def rename_item(self, board_id: str, item_id: str, name: str) -> None:
        q = """mutation ($board: ID!, $item: ID!, $name: String!) {
          change_simple_column_value (board_id: $board, item_id: $item, column_id: "name", value: $name) { id }
        }"""
        self._gql(q, {"board": str(board_id), "item": str(item_id), "name": name})

    def delete_item(self, item_id: str) -> None:
        q = "mutation ($item: ID!) { delete_item (item_id: $item) { id } }"
        self._gql(q, {"item": str(item_id)})

    def _gql(self, query: str, variables: dict | None = None) -> dict:
        token = settings.monday_token or ""
        body: dict = {"query": query}
        if variables is not None:
            body["variables"] = variables
        try:
            resp = httpx.post(
                settings.monday_api,
                headers={
                    "Authorization": token,
                    "Content-Type": "application/json",
                    "API-Version": "2024-10",
                },
                json=body,
                timeout=20.0,
            )
        except httpx.HTTPError as exc:  # transport error
            raise MondayApiError(str(exc)) from exc
        if resp.status_code >= 400:
            raise MondayApiError(f"monday.com API {resp.status_code}", resp.status_code)
        payload = resp.json()
        if payload.get("errors"):
            raise MondayApiError(str(payload["errors"]))
        return payload.get("data") or {}
