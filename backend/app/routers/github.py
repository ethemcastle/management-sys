"""GitHub endpoints: connect a repo, then identify branches/PRs for a ticket by
its code (issue key)."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import get_issue_or_404
from app.models.github import GitHubRepo, RepoBranch, RepoPullRequest
from app.models.issue import Issue
from app.models.member import TeamMember
from app.schemas.entities import CheckOut, MemberRef, PullRequestOut
from app.schemas.github import BranchOut, ConnectBody, ConnectResult, LinksOut, RepoOut
from app.services.github_service import GitHubService, get_github_service

router = APIRouter(prefix="/api/github", tags=["github"])


def _members(db: Session) -> dict[str, TeamMember]:
    return {m.initials: m for m in db.scalars(select(TeamMember))}


def _member_ref(initials: str | None, members: dict[str, TeamMember]) -> MemberRef | None:
    m = members.get(initials or "")
    return MemberRef(initials=m.initials, name=m.name, color=m.color) if m else None


def _branch_out(b: RepoBranch, members: dict[str, TeamMember]) -> BranchOut:
    return BranchOut(
        name=b.name,
        ahead=b.ahead,
        behind=b.behind,
        last_commit=b.last_commit,
        author=_member_ref(b.author_initials, members),
        updated_at=b.updated_at,
    )


def _pr_out(p: RepoPullRequest) -> PullRequestOut:
    return PullRequestOut(
        num=p.number,
        title=p.title,
        branch=p.branch,
        state=p.state,
        checks=p.checks,
        checks_detail=[CheckOut(**c) for c in (p.checks_detail or [])],
        additions=p.additions,
        deletions=p.deletions,
        files_changed=p.files_changed,
        ai_generated=p.ai_generated,
        reviewers=[],
    )


def _repo_out(repo: GitHubRepo) -> RepoOut:
    return RepoOut.model_validate(repo)


@router.get("/repo", response_model=RepoOut)
def get_repo(
    db: Session = Depends(get_db),
    gh: GitHubService = Depends(get_github_service),
) -> RepoOut:
    return _repo_out(gh.get_repo(db))


@router.post("/connect", response_model=ConnectResult)
def connect(
    payload: ConnectBody,
    db: Session = Depends(get_db),
    gh: GitHubService = Depends(get_github_service),
) -> ConnectResult:
    try:
        branches, prs = gh.connect(db, payload.full_name.strip())
    except Exception as exc:  # live GitHub errors (bad repo / auth / rate limit)
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return ConnectResult(repo=_repo_out(gh.get_repo(db)), branches=branches, pull_requests=prs)


@router.post("/sync", response_model=ConnectResult)
def sync(
    db: Session = Depends(get_db),
    gh: GitHubService = Depends(get_github_service),
) -> ConnectResult:
    """Re-pull the connected repo's branches/PRs from GitHub right now."""
    repo = gh.get_repo(db)
    if not repo.connected or not repo.full_name:
        raise HTTPException(status_code=400, detail="No repository connected")
    try:
        branches, prs = gh.connect(db, repo.full_name)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return ConnectResult(repo=_repo_out(gh.get_repo(db)), branches=branches, pull_requests=prs)


@router.post("/disconnect", response_model=RepoOut)
def disconnect(
    db: Session = Depends(get_db),
    gh: GitHubService = Depends(get_github_service),
) -> RepoOut:
    return _repo_out(gh.disconnect(db))


@router.get("/issues/{key}/links", response_model=LinksOut)
def issue_links(
    issue: Issue = Depends(get_issue_or_404),
    db: Session = Depends(get_db),
    gh: GitHubService = Depends(get_github_service),
) -> LinksOut:
    repo = gh.get_repo(db)
    branches, prs = ([], []) if not repo.connected else gh.links(db, issue.key)
    members = _members(db)
    return LinksOut(
        repo=_repo_out(repo),
        key=issue.key,
        branches=[_branch_out(b, members) for b in branches],
        prs=[_pr_out(p) for p in prs],
    )
