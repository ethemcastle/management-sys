"""Role dashboard endpoint — developer or product-owner Home data.

Returned as a role-tagged wrapper (`{ role, developer? , po? }`) so the client
can switch on `role` without guessing which shape it received.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.db import get_db
from app.models.enums import Role, Space
from app.schemas.views import DashboardOut
from app.services import metrics

router = APIRouter(prefix="/api", tags=["dashboard"])


@router.get("/dashboard", response_model=DashboardOut)
def get_dashboard(
    role: Role = Query(Role.developer),
    space: Space = Query(Space.features),
    db: Session = Depends(get_db),
) -> DashboardOut:
    if role == Role.product_owner:
        return DashboardOut(role=role, po=metrics.build_dashboard_po(db, space))
    return DashboardOut(role=role, developer=metrics.build_dashboard_developer(db, space))
