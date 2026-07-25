"""Catalog of user-managed option lists (Products, Components, Releases).

These populate the ticket "Information" fields — created/renamed/deleted from the
Settings page. Kept deliberately generic (one table, a `kind` discriminator) so
new managed lists are a one-line addition.
"""
from __future__ import annotations

from sqlalchemy import Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base

# Allowed catalog kinds (also the API's ?kind= values).
CATALOG_KINDS = ("product", "component", "release")


class CatalogItem(Base):
    __tablename__ = "catalog_items"
    __table_args__ = (UniqueConstraint("kind", "name", name="uq_catalog_kind_name"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    kind: Mapped[str] = mapped_column(String(24))  # product | component | release
    name: Mapped[str] = mapped_column(String(120))
