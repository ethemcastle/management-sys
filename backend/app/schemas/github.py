"""GitHub integration schemas (camelCase JSON)."""
from __future__ import annotations

from datetime import datetime

from app.schemas.common import CamelModel
from app.schemas.entities import MemberRef, PullRequestOut


class RepoOut(CamelModel):
    connected: bool
    owner: str | None = None
    name: str | None = None
    full_name: str | None = None
    default_branch: str = "main"
    connected_at: datetime | None = None


class BranchOut(CamelModel):
    name: str
    ahead: int = 0
    behind: int = 0
    last_commit: str = ""
    author: MemberRef | None = None
    updated_at: datetime


class LinksOut(CamelModel):
    """Branches + PRs from the connected repo that reference the ticket key."""

    repo: RepoOut
    key: str
    branches: list[BranchOut]
    prs: list[PullRequestOut]


class ConnectBody(CamelModel):
    full_name: str  # "owner/repo"


class ConnectResult(CamelModel):
    repo: RepoOut
    branches: int
    pull_requests: int
