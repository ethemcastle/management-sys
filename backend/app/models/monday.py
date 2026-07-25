"""monday.com models: a connection, imported boards, and their items.

The monday.com link is mocked behind a `MockMondayService` seam; connecting
imports boards/items into these rows. A `LiveMondayService` (activated when
`CADENCE_MONDAY_TOKEN` is set) swaps in without any API/frontend change.

`MondayItem.issue_key` is a soft link (not an enforced FK) to the Cadence Issue
created when the item is imported "as a ticket" — so deleting that issue never
blocks, it just leaves the item importable again.
"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class MondayAccount(Base):
    """Single-row connection state for the (mock) monday.com link."""

    __tablename__ = "monday_account"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    connected: Mapped[bool] = mapped_column(Boolean, default=False)
    account_name: Mapped[str | None] = mapped_column(String(160), nullable=True)
    connected_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class MondayBoard(Base):
    __tablename__ = "monday_boards"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    board_id: Mapped[str] = mapped_column(String(48))  # monday's board id
    name: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text, default="")
    kind: Mapped[str] = mapped_column(String(24), default="public")
    url: Mapped[str | None] = mapped_column(String(400), nullable=True)
    # Per-board write metadata (needed to push values back to the right monday
    # column). columns_meta: [{id, title, type, labels}] (labels for status cols);
    # groups: [{id, title}] where groups[0] is the default landing group.
    columns_meta: Mapped[list[dict]] = mapped_column(JSON, default=list)
    groups: Mapped[list[dict]] = mapped_column(JSON, default=list)

    items: Mapped[list[MondayItem]] = relationship(
        "MondayItem",
        back_populates="board",
        order_by="MondayItem.position",
        cascade="all, delete-orphan",
    )


class MondayItem(Base):
    __tablename__ = "monday_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    board_pk: Mapped[int] = mapped_column(ForeignKey("monday_boards.id"))
    item_id: Mapped[str] = mapped_column(String(48))  # monday's item (pulse) id
    name: Mapped[str] = mapped_column(String(400))
    group_title: Mapped[str] = mapped_column(String(120), default="")
    status_label: Mapped[str | None] = mapped_column(String(80), nullable=True)
    status_color: Mapped[str | None] = mapped_column(String(9), nullable=True)
    # Owner: {name, initials, color} or null
    owner_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    owner_initials: Mapped[str | None] = mapped_column(String(4), nullable=True)
    owner_color: Mapped[str | None] = mapped_column(String(9), nullable=True)
    url: Mapped[str | None] = mapped_column(String(400), nullable=True)
    updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    position: Mapped[int] = mapped_column(Integer, default=0)
    # Full column snapshot from monday: list of {title, text, type} — everything on
    # the item, saved so the data lives in Cadence without opening monday.
    columns: Mapped[list[dict]] = mapped_column(JSON, default=list)

    # Soft link to the Cadence Issue created when this item is imported as a ticket.
    issue_key: Mapped[str | None] = mapped_column(String(24), nullable=True)

    board: Mapped[MondayBoard] = relationship("MondayBoard", back_populates="items")
