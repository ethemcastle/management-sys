"""GitHub integration models: a (mock) repository connection plus pools of
branches and pull requests that are matched to tickets by the ticket code
(issue key) found in the branch name or PR title.

Mocked behind a `MockGitHubService` seam; a real GitHub App/API implementation
can populate these rows later without changing the API or the frontend.
"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import JSON, Boolean, DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base
from app.models.enums import CiStatus, PrState


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class GitHubRepo(Base):
    """Single-row connection state for the linked repository."""

    __tablename__ = "github_repo"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    connected: Mapped[bool] = mapped_column(Boolean, default=False)
    owner: Mapped[str | None] = mapped_column(String(120), nullable=True)
    name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    full_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    default_branch: Mapped[str] = mapped_column(String(80), default="main")
    connected_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class RepoBranch(Base):
    __tablename__ = "repo_branches"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(200))
    ahead: Mapped[int] = mapped_column(Integer, default=0)
    behind: Mapped[int] = mapped_column(Integer, default=0)
    last_commit: Mapped[str] = mapped_column(String(255), default="")
    author_initials: Mapped[str | None] = mapped_column(String(4), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


class RepoPullRequest(Base):
    __tablename__ = "repo_pull_requests"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    number: Mapped[int] = mapped_column(Integer, unique=True)
    title: Mapped[str] = mapped_column(String(255))
    branch: Mapped[str] = mapped_column(String(200))
    base: Mapped[str] = mapped_column(String(80), default="main")
    state: Mapped[PrState] = mapped_column(default=PrState.open)
    checks: Mapped[CiStatus] = mapped_column(default=CiStatus.pending)
    # Real per-check status from GitHub: list of {name, status} (status ∈ passing|failing|pending).
    checks_detail: Mapped[list[dict]] = mapped_column(JSON, default=list)
    additions: Mapped[int] = mapped_column(Integer, default=0)
    deletions: Mapped[int] = mapped_column(Integer, default=0)
    files_changed: Mapped[int] = mapped_column(Integer, default=0)
    author_initials: Mapped[str | None] = mapped_column(String(4), nullable=True)
    ai_generated: Mapped[bool] = mapped_column(Boolean, default=False)
