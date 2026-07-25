"""Bootstrap endpoint — everything static the app shell needs at load."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.deps import get_current_user
from app.db import get_db
from app.models.member import TeamMember
from app.models.sprint import Sprint
from app.schemas.entities import MemberOut, SpaceOut, SprintOut
from app.schemas.views import BootstrapOut
from app.services import catalog

router = APIRouter(prefix="/api", tags=["meta"])


@router.get("/bootstrap", response_model=BootstrapOut)
def bootstrap(
    db: Session = Depends(get_db),
    current: TeamMember = Depends(get_current_user),
) -> BootstrapOut:
    members = list(db.scalars(select(TeamMember).order_by(TeamMember.name)))
    sprints = list(db.scalars(select(Sprint).order_by(Sprint.id)))
    return BootstrapOut(
        current_user=MemberOut.model_validate(current),
        members=[MemberOut.model_validate(m) for m in members],
        spaces=[SpaceOut(**s) for s in catalog.spaces()],
        sprints=[SprintOut.model_validate(s) for s in sprints],
        labels=catalog.label_colors(),
    )
