"""Sprint model."""
from __future__ import annotations

from sqlalchemy import Boolean, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class Sprint(Base):
    __tablename__ = "sprints"

    id: Mapped[str] = mapped_column(String(16), primary_key=True)  # "s24"
    name: Mapped[str] = mapped_column(String(80))
    range: Mapped[str] = mapped_column(String(80))
    goal: Mapped[str] = mapped_column(String(255), default="")
    days_left: Mapped[int | None] = mapped_column(Integer, nullable=True)
    days_total: Mapped[int] = mapped_column(Integer, default=10)
    capacity: Mapped[int | None] = mapped_column(Integer, nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, default=False)
