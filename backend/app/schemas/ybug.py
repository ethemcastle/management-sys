"""Ybug schemas (camelCase JSON)."""
from __future__ import annotations

from datetime import datetime

from app.schemas.common import CamelModel


class YbugAccountOut(CamelModel):
    connected: bool
    project_name: str | None = None
    connected_at: datetime | None = None
    ticket_count: int = 0


class YbugSyncResult(CamelModel):
    account: YbugAccountOut
    created: int
    keys: list[str] = []
