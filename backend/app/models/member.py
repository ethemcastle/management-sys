"""TeamMember model — keyed by 2-letter initials."""
from __future__ import annotations

from sqlalchemy import Boolean, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class TeamMember(Base):
    __tablename__ = "members"

    initials: Mapped[str] = mapped_column(String(4), primary_key=True)  # "AL"
    name: Mapped[str] = mapped_column(String(120))
    color: Mapped[str] = mapped_column(String(9))  # "#0E7C86"
    role: Mapped[str] = mapped_column(String(20))  # developer | product_owner
    is_current_user: Mapped[bool] = mapped_column(Boolean, default=False)
