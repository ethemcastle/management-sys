"""AI endpoints (the differentiator). Backed by `AiService`; ships with the
deterministic `MockAiService`. Latency is simulated so the UI's loading states
read naturally even against a fast backend.
"""
from __future__ import annotations

import logging
import time

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.db import get_db
from app.deps import get_issue_or_404
from app.models.comment import Comment
from app.models.issue import Issue
from app.models.member import TeamMember
from app.models.pull_request import PullRequest
from app.schemas.ai import (
    AssistantResponse,
    CreatePrResponse,
    SolveResponse,
    SuggestedResolution,
    SummarizeResponse,
)
from app.schemas.entities import CommentOut
from app.schemas.requests import AnswerRequest, AssistantRequest
from app.services import serializers as S
from app.services.ai_service import AiService, get_ai_service
from app.services.github_service import GitHubService, get_github_service

router = APIRouter(prefix="/api/ai", tags=["ai"])
log = logging.getLogger("cadence.ai")


def _open_pr(db: Session, issue: Issue, ai: AiService, github: GitHubService) -> PullRequest:
    """Open a REAL pull request on the connected repo when possible; otherwise the
    deterministic mock PR. Real creation needs a live, connected, *writable* repo —
    a read-only token (or no repo) transparently falls back to the mock."""
    from app.services.github_live import GitHubApiError, LiveGitHubService

    if isinstance(github, LiveGitHubService):
        repo = github.get_repo(db)
        if repo.connected and repo.full_name:
            try:
                # Code-gen: search the repo and derive real edits from the ticket.
                # Empty result (or any failure) → placeholder commit, never a hard error.
                edits: list[dict] = []
                try:
                    from app.services import codegen

                    edits = codegen.build_edits(issue, github, repo)
                except Exception as e:
                    log.warning("codegen failed (%s) — opening a placeholder PR", e)
                real = github.open_pull_request(db, issue, commit_files=edits or None)
                return _mirror_pr(db, issue, real)
            except GitHubApiError as e:
                log.warning("real PR open failed (%s) — falling back to mock", e)
    return ai.create_pr(db, issue)


def _mirror_pr(db: Session, issue: Issue, real: dict) -> PullRequest:
    """Reflect a real GitHub PR into a risr/crm PullRequest row so the issue's PR
    badge and the ticket-code-linked panel agree. Also removes any previously
    fabricated mock PRs for this issue (num in the mock range) so real and mock
    PRs never pile up on the same ticket."""
    from app.models.enums import CiStatus, PrState
    from app.services.ai_service import AI_PR_BASE

    num = real["number"]
    pr = db.get(PullRequest, num)
    if pr is None:
        pr = PullRequest(num=num, issue_key=issue.key)
        db.add(pr)
    pr.issue_key = issue.key
    pr.title = f"{issue.key}: {issue.title}"
    pr.branch = real["branch"]
    pr.state = PrState.open
    pr.checks = CiStatus.pending
    pr.additions, pr.deletions, pr.files_changed = 1, 0, max(1, len(real.get("changed") or []))
    pr.ai_generated = True
    db.flush()

    # Drop stale fabricated mock PRs for this issue (mock nums start at AI_PR_BASE);
    # real GitHub PR numbers are far below that, so this only clears the fakes.
    for old in list(issue.prs):
        if old.num != num and old.ai_generated and old.num >= AI_PR_BASE:
            db.delete(old)
    db.flush()
    db.refresh(issue)
    return pr


def _dwell() -> None:
    """Hold briefly so the client's spinner transition reads. Skipped when a real
    AI model is wired in — it supplies its own (real) latency."""
    if not settings.ai_api_key and settings.ai_latency_seconds > 0:
        time.sleep(settings.ai_latency_seconds)


@router.post("/issues/{key}/summarize", response_model=SummarizeResponse)
def summarize_issue(
    issue: Issue = Depends(get_issue_or_404),
    ai: AiService = Depends(get_ai_service),
) -> SummarizeResponse:
    _dwell()
    result = ai.summarize(issue)
    return SummarizeResponse(
        bullets=result.bullets,
        suggested_resolution=SuggestedResolution(summary=result.summary, files=result.files),
    )


@router.post("/issues/{key}/create-pr", response_model=CreatePrResponse)
def create_pr(
    issue: Issue = Depends(get_issue_or_404),
    db: Session = Depends(get_db),
    ai: AiService = Depends(get_ai_service),
    github: GitHubService = Depends(get_github_service),
) -> CreatePrResponse:
    _dwell()
    pr = _open_pr(db, issue, ai, github)
    db.commit()
    db.refresh(issue)
    return CreatePrResponse(pr=S.pr_out(pr), issue=S.issue_detail(issue))


@router.post("/tickets/{key}/solve", response_model=SolveResponse)
def solve_ticket(
    issue: Issue = Depends(get_issue_or_404),
    db: Session = Depends(get_db),
    ai: AiService = Depends(get_ai_service),
    github: GitHubService = Depends(get_github_service),
) -> SolveResponse:
    _dwell()
    # Real AI diagnosis (Groq when configured) + a real PR when the repo is writable.
    summ = ai.summarize(issue)
    pr = _open_pr(db, issue, ai, github)
    summary = (
        f"risr/crm AI diagnosed {issue.key}: {summ.summary} "
        f"Opened PR #{pr.num} on `{pr.branch}` with the change."
    )
    db.commit()
    db.refresh(issue)
    return SolveResponse(
        pr=S.pr_out(pr),
        summary=summary,
        files=summ.files,
        issue=S.issue_detail(issue),
    )


@router.post("/assistant", response_model=AssistantResponse)
def assistant(
    payload: AssistantRequest,
    ai: AiService = Depends(get_ai_service),
) -> AssistantResponse:
    _dwell()
    return AssistantResponse(bullets=ai.assistant(payload.question, payload.context))


@router.post("/issues/{key}/answer", response_model=CommentOut, status_code=201)
def answer_comment(
    payload: AnswerRequest,
    issue: Issue = Depends(get_issue_or_404),
    db: Session = Depends(get_db),
    github: GitHubService = Depends(get_github_service),
) -> CommentOut:
    """Answer an @AI comment: research the connected repo's code, then post the
    answer as an AI-authored reply on the ticket's activity feed."""
    from app.services import codegen
    from app.services.github_live import LiveGitHubService

    gh = github if isinstance(github, LiveGitHubService) else None
    repo = gh.get_repo(db) if gh is not None else None
    answer = codegen.answer_question(issue, payload.question, gh, repo)

    # AI comments render via a synthetic "risr/crm AI" author (kind="ai"); the stored
    # author_initials just satisfies the FK.
    author = db.scalars(select(TeamMember).where(TeamMember.is_current_user.is_(True))).first()
    if author is None:
        author = db.scalars(select(TeamMember)).first()
    comment = Comment(
        issue_key=issue.key,
        author_initials=author.initials if author else None,
        kind="ai",
        body=answer,
    )
    db.add(comment)
    issue.comment_count += 1
    db.commit()
    db.refresh(comment)
    return S.comment_out(comment)
