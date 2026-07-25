"""AI endpoint response schemas."""
from __future__ import annotations

from app.schemas.common import CamelModel
from app.schemas.entities import IssueDetailOut, PullRequestOut


class SuggestedResolution(CamelModel):
    summary: str
    files: list[str]


class SummarizeResponse(CamelModel):
    bullets: list[str]
    suggested_resolution: SuggestedResolution


class CreatePrResponse(CamelModel):
    pr: PullRequestOut
    issue: IssueDetailOut


class SolveResponse(CamelModel):
    pr: PullRequestOut
    summary: str
    files: list[str]
    issue: IssueDetailOut


class AssistantResponse(CamelModel):
    bullets: list[str]
