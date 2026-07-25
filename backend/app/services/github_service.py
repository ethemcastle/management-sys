"""GitHub behind an interface.

`GitHubService` is the seam; `MockGitHubService` ships by default. Connecting a
repo "imports" a pool of branches and pull requests whose names embed the ticket
code (issue key). Linking a ticket then just filters that pool by the key found
in the branch name or PR title — exactly what a real GitHub App would surface.

Swap in a real implementation (GitHub REST/GraphQL) via `get_github_service()`;
the API and frontend never change.
"""
from __future__ import annotations

import re
from abc import ABC, abstractmethod
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.enums import CiStatus, IssueType, PrState
from app.models.github import GitHubRepo, RepoBranch, RepoPullRequest
from app.models.issue import Issue

_NOISE_BRANCHES = [
    ("main", 0, 0, "Merge pull request into main"),
    ("develop", 3, 1, "Sync develop with main"),
    ("chore/bump-deps", 2, 0, "chore: bump dependencies"),
    ("docs/update-readme", 1, 0, "docs: refresh the README"),
]


def _stable_hash(s: str) -> int:
    return sum(ord(c) for c in s)


def _slug(title: str) -> str:
    words = re.sub(r"[^a-z0-9 ]", "", title.lower()).split()
    return "-".join(words[:4])


def _branch_name(issue: Issue) -> str:
    prefix = "fix" if issue.type == IssueType.bug else "feat"
    return f"{prefix}/{issue.key.lower()}-{_slug(issue.title)}"


class GitHubService(ABC):
    @abstractmethod
    def connect(self, db: Session, full_name: str) -> tuple[int, int]: ...

    @abstractmethod
    def get_repo(self, db: Session) -> GitHubRepo: ...

    @abstractmethod
    def disconnect(self, db: Session) -> GitHubRepo: ...

    @abstractmethod
    def links(self, db: Session, key: str) -> tuple[list[RepoBranch], list[RepoPullRequest]]: ...


class MockGitHubService(GitHubService):
    def get_repo(self, db: Session) -> GitHubRepo:
        repo = db.scalars(select(GitHubRepo)).first()
        if repo is None:
            repo = GitHubRepo(connected=False)
            db.add(repo)
            db.commit()
            db.refresh(repo)
        return repo

    def connect(self, db: Session, full_name: str) -> tuple[int, int]:
        repo = self.get_repo(db)
        owner, _, name = full_name.partition("/")
        repo.connected = True
        repo.owner = owner or "northwind"
        repo.name = name or full_name
        repo.full_name = full_name if "/" in full_name else f"northwind/{full_name}"
        repo.default_branch = "main"
        repo.connected_at = datetime.now(timezone.utc)

        # Import the branch/PR pool once (idempotent re-connect = a sync no-op).
        if db.scalar(select(func.count()).select_from(RepoBranch)) == 0:
            self._import_pool(db)
        db.commit()
        branches = db.scalar(select(func.count()).select_from(RepoBranch)) or 0
        prs = db.scalar(select(func.count()).select_from(RepoPullRequest)) or 0
        return branches, prs

    def disconnect(self, db: Session) -> GitHubRepo:
        repo = self.get_repo(db)
        repo.connected = False
        db.commit()
        db.refresh(repo)
        return repo

    def _import_pool(self, db: Session) -> None:
        for name, ahead, behind, msg in _NOISE_BRANCHES:
            db.add(RepoBranch(name=name, ahead=ahead, behind=behind, last_commit=msg))

        issues = db.scalars(
            select(Issue).where(Issue.type != IssueType.epic).order_by(Issue.key)
        )
        for issue in issues:
            h = _stable_hash(issue.key)
            bname = _branch_name(issue)
            db.add(
                RepoBranch(
                    name=bname,
                    ahead=(h % 9) + 1,
                    behind=h % 4,
                    last_commit=f"{issue.key}: {issue.title}",
                    author_initials=issue.assignee_initials,
                )
            )
            pr = issue.pr
            if pr is not None:
                db.add(
                    RepoPullRequest(
                        number=pr.num,
                        title=f"{issue.key}: {pr.title}",
                        branch=bname,
                        base="main",
                        state=pr.state,
                        checks=pr.checks,
                        additions=pr.additions,
                        deletions=pr.deletions,
                        files_changed=pr.files_changed,
                        author_initials=issue.assignee_initials,
                        ai_generated=pr.ai_generated,
                    )
                )
        db.flush()

    def links(self, db: Session, key: str) -> tuple[list[RepoBranch], list[RepoPullRequest]]:
        k = key.lower()
        branches = [
            b for b in db.scalars(select(RepoBranch).order_by(RepoBranch.name)) if k in b.name.lower()
        ]
        prs = [
            p
            for p in db.scalars(select(RepoPullRequest).order_by(RepoPullRequest.number))
            if k in p.title.lower() or k in p.branch.lower()
        ]
        return branches, prs


_mock_service: GitHubService = MockGitHubService()
_live_service: GitHubService | None = None


def get_github_service() -> GitHubService:
    """FastAPI dependency. Uses the live GitHub API when a token is configured
    (`CADENCE_GITHUB_TOKEN`), otherwise the offline mock."""
    from app.config import settings

    if settings.github_token:
        global _live_service
        if _live_service is None:
            from app.services.github_live import LiveGitHubService

            _live_service = LiveGitHubService()
        return _live_service
    return _mock_service
