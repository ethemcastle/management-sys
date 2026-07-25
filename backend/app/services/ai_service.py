"""AI behind an interface.

`AiService` is the abstract seam; `MockAiService` ships by default and returns
deterministic, correctly-shaped responses so the whole app is demoable offline.
To plug in a real model later, implement `AiService` (e.g. `LlmAiService`) and
swap the instance returned by `get_ai_service()` — no endpoint or schema changes.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.enums import CiStatus, PrState
from app.models.issue import Issue
from app.models.pull_request import PullRequest
from app.schemas.entities import DescriptionBlock  # noqa: F401  (kept for type parity)
from app.schemas.requests import AssistantContext

# First AI PR number matches the design prototype (#834); subsequent ones grow.
AI_PR_BASE = 834


@dataclass
class Summary:
    bullets: list[str]
    summary: str
    files: list[str]


@dataclass
class Solved:
    pr: PullRequest
    summary: str
    files: list[str]


class AiService(ABC):
    @abstractmethod
    def summarize(self, issue: Issue) -> Summary: ...

    @abstractmethod
    def create_pr(self, db: Session, issue: Issue) -> PullRequest: ...

    @abstractmethod
    def solve(self, db: Session, issue: Issue) -> Solved: ...

    @abstractmethod
    def assistant(self, question: str, context: AssistantContext) -> list[str]: ...


def _affected_files(issue: Issue) -> list[str]:
    """Deterministic, plausible file list derived from the issue's labels/type."""
    labels = set(issue.labels or [])
    slug = issue.title.lower().split()
    stem = "-".join(slug[:3]) if slug else issue.key.lower()
    files: list[str] = []
    if "frontend" in labels or "design" in labels or "mobile" in labels:
        files.append(f"frontend/src/app/features/{stem}.component.ts")
    if "backend" in labels or "api" in labels or "infra" in labels:
        files.append(f"backend/app/services/{stem.replace('-', '_')}.py")
    if issue.type.value == "bug":
        files.append(f"backend/tests/test_{stem.replace('-', '_')}.py")
    if not files:
        files.append(f"src/{stem}.ts")
    return files[:3]


class MockAiService(AiService):
    """Deterministic mock. Every response is shaped exactly like the contract."""

    def summarize(self, issue: Issue) -> Summary:
        who = issue.assignee.name if issue.assignee else "The team"
        pr = issue.pr
        bullets: list[str] = [
            f"{who} scoped {issue.key} — “{issue.title}” ({issue.points} pts, "
            f"priority {['Low', 'Medium', 'High', 'Urgent'][issue.priority]}).",
        ]
        if pr:
            state = {PrState.open: "open", PrState.draft: "a draft", PrState.merged: "merged"}[pr.state]
            bullets.append(
                f"PR #{pr.num} on `{pr.branch}` is {state} with "
                f"+{pr.additions}/−{pr.deletions} across {pr.files_changed} files."
            )
            check = {
                CiStatus.passing: "CI is green",
                CiStatus.failing: "CI is failing — needs a fix before merge",
                CiStatus.pending: "CI is still running",
            }[pr.checks]
            bullets.append(f"{check}.")
            if pr.reviewers:
                names = ", ".join(r.member.name for r in pr.reviewers)
                bullets.append(f"Review requested from {names}; some notes are outstanding.")
        else:
            bullets.append("No branch or PR yet — this issue is unstarted from a code perspective.")
        if issue.comment_count:
            bullets.append(f"The thread has {issue.comment_count} comments discussing edge cases.")
        net = "ready for review" if (pr and pr.checks == CiStatus.passing) else "still needs work"
        bullets.append(f"Net: {issue.key} is {net}.")

        files = _affected_files(issue)
        summary = (
            f"Address {issue.title.lower()} by updating the affected modules and adding a "
            f"regression test. The change is small and localized."
        )
        return Summary(bullets=bullets[:5], summary=summary, files=files)

    def create_pr(self, db: Session, issue: Issue) -> PullRequest:
        num = self._next_pr_num(db)
        pr = PullRequest(
            num=num,
            issue_key=issue.key,
            title=f"AI fix: {issue.title}",
            branch=f"cadence-ai/{issue.key.lower()}-fix",
            state=PrState.open,
            checks=CiStatus.pending,
            additions=64,
            deletions=12,
            files_changed=3,
            ai_generated=True,
        )
        db.add(pr)
        db.flush()
        db.refresh(issue)
        return pr

    def solve(self, db: Session, issue: Issue) -> Solved:
        summ = self.summarize(issue)
        pr = self.create_pr(db, issue)
        summary = (
            f"risr/crm AI diagnosed {issue.key}: {summ.summary} Opened PR #{pr.num} on "
            f"`{pr.branch}` with the fix and a regression test."
        )
        return Solved(pr=pr, summary=summary, files=summ.files)

    def assistant(self, question: str, context: AssistantContext) -> list[str]:
        where = f"{context.view} · {context.space.value}"
        q = question.strip().lower()
        if "risk" in q:
            return [
                "Billing webhook bug CAD-138 has failing CI — highest risk to the sprint goal.",
                "Auth-cookie migration CAD-162 is blocked and unstarted (8 pts).",
                "Realtime cursors CAD-129 is large (8 pts) and still in progress.",
                "Net: 2 items need attention today to keep Sprint 24 on track.",
            ]
        if "release notes" in q or "notes" in q:
            return [
                "Proration on plan change (CAD-140) shipped — smoother mid-cycle upgrades.",
                "Fixed a timezone off-by-one in due dates (CAD-145).",
                "Dark mode audit for the board view landed (CAD-158).",
                "Net: 3 user-facing improvements merged this sprint.",
            ]
        if "stale" in q or "pr" in q:
            return [
                "PR #808 (realtime cursors) is a draft with pending checks — 4 days idle.",
                "PR #814 (billing webhook) has failing CI and is blocking CAD-138.",
                "Net: nudge 2 PRs to keep the pipeline moving.",
            ]
        if "sprint" in q or "summarize" in q:
            return [
                "Sprint 24 goal: Onboarding v2 & billing stability.",
                "10 of 45 committed points done; 16 in progress, 8 in review.",
                "Main risks: billing CI failure and the blocked auth migration.",
                "Net: on track if the two risks clear this week.",
            ]
        return [
            f"Looking at {where}.",
            "I can summarize the sprint, flag risks, draft release notes, or find stale PRs.",
            "Ask me anything about this workspace — I read the issues, PRs, and CI live.",
        ]

    @staticmethod
    def _next_pr_num(db: Session) -> int:
        max_num = db.scalar(select(func.max(PullRequest.num))) or 0
        return max(AI_PR_BASE, max_num + 1)


_service: AiService = MockAiService()
_live_service: AiService | None = None


def get_ai_service() -> AiService:
    """FastAPI dependency. Uses the live LLM service when an API key is configured
    (`CADENCE_AI_API_KEY`), otherwise the deterministic offline mock."""
    from app.config import settings

    if settings.ai_api_key:
        global _live_service
        if _live_service is None:
            from app.services.ai_live import LiveAiService

            _live_service = LiveAiService()
        return _live_service
    return _service
