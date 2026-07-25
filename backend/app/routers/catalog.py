"""Catalog endpoints: manage the option lists (Products, Components, Releases)
that populate ticket "Information" fields. CRUD from the Settings page."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models.catalog import CATALOG_KINDS, CatalogItem
from app.schemas.entities import CatalogItemCreate, CatalogItemOut, CatalogItemPatch

router = APIRouter(prefix="/api/catalog", tags=["catalog"])


def _out(item: CatalogItem) -> CatalogItemOut:
    return CatalogItemOut(id=item.id, kind=item.kind, name=item.name)


@router.get("", response_model=list[CatalogItemOut])
def list_items(
    kind: str | None = Query(None), db: Session = Depends(get_db)
) -> list[CatalogItemOut]:
    stmt = select(CatalogItem).order_by(CatalogItem.kind, CatalogItem.name)
    if kind is not None:
        stmt = stmt.where(CatalogItem.kind == kind)
    return [_out(i) for i in db.scalars(stmt)]


@router.post("", response_model=CatalogItemOut, status_code=201)
def create_item(payload: CatalogItemCreate, db: Session = Depends(get_db)) -> CatalogItemOut:
    kind = payload.kind.strip().lower()
    name = payload.name.strip()
    if kind not in CATALOG_KINDS:
        raise HTTPException(status_code=422, detail=f"Unknown kind '{kind}'")
    if not name:
        raise HTTPException(status_code=422, detail="Name is required")
    # Idempotent: return the existing item if it already exists (case-insensitive).
    existing = db.scalars(
        select(CatalogItem).where(
            CatalogItem.kind == kind, func.lower(CatalogItem.name) == name.lower()
        )
    ).first()
    if existing is not None:
        return _out(existing)
    item = CatalogItem(kind=kind, name=name)
    db.add(item)
    db.commit()
    db.refresh(item)
    return _out(item)


@router.patch("/{item_id}", response_model=CatalogItemOut)
def rename_item(
    item_id: int, payload: CatalogItemPatch, db: Session = Depends(get_db)
) -> CatalogItemOut:
    item = db.get(CatalogItem, item_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Item not found")
    name = payload.name.strip()
    if not name:
        raise HTTPException(status_code=422, detail="Name is required")
    item.name = name
    db.commit()
    db.refresh(item)
    return _out(item)


@router.delete("/{item_id}", status_code=204)
def delete_item(item_id: int, db: Session = Depends(get_db)) -> None:
    item = db.get(CatalogItem, item_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Item not found")
    db.delete(item)
    db.commit()
