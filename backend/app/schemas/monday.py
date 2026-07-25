"""monday.com schemas (camelCase JSON)."""
from __future__ import annotations

from datetime import datetime

from app.schemas.common import CamelModel


class MondayOwner(CamelModel):
    name: str
    initials: str
    color: str


class MondayColumn(CamelModel):
    title: str
    value: str


class MondayGroup(CamelModel):
    id: str
    title: str


class MondayItemOut(CamelModel):
    id: int
    item_id: str
    name: str
    group: str = ""
    status_label: str | None = None
    status_color: str | None = None
    owner: MondayOwner | None = None
    url: str | None = None
    updated_at: datetime | None = None
    columns: list[MondayColumn] = []
    issue_key: str | None = None
    imported: bool = False


class MondayBoardOut(CamelModel):
    id: int
    board_id: str
    name: str
    description: str = ""
    kind: str = "public"
    url: str | None = None
    groups: list[MondayGroup] = []
    item_count: int = 0
    items: list[MondayItemOut] = []


class MondayAccountOut(CamelModel):
    connected: bool
    account_name: str | None = None
    connected_at: datetime | None = None


class MondayOut(CamelModel):
    account: MondayAccountOut
    boards: list[MondayBoardOut] = []


class MondayConnectResult(CamelModel):
    account: MondayAccountOut
    boards: int
    items: int
    imported: int = 0  # tickets created from monday items this call
    pulled: int = 0  # existing linked tickets updated from monday
    pushed: int = 0  # local/pending tickets pushed to monday


class MondayImportResult(CamelModel):
    item: MondayItemOut
    issue_key: str
