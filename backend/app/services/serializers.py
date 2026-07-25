"""ORM -> Pydantic serializers producing the denormalized, display-ready shapes.

Keeping the mapping in one place means every endpoint returns issues in an
identical shape (cards, lists, board, dashboards, detail all agree).
"""
from __future__ import annotations

import re

from app.models.comment import Comment
from app.models.enums import IssueType, Status
from app.models.issue import Issue
from app.models.member import TeamMember
from app.models.pull_request import PullRequest
from app.schemas.entities import (
    AuditEntryOut,
    ChildProgress,
    CommentOut,
    DescriptionBlock,
    FeatureRef,
    IssueDetailOut,
    IssueOut,
    LabelOut,
    MemberOut,
    MemberRef,
    MondayFieldOut,
    PullRequestOut,
    ReviewerOut,
)
from app.services.catalog import label_color

DONE = Status.done


def member_ref(member: TeamMember | None) -> MemberRef | None:
    if member is None:
        return None
    return MemberRef(initials=member.initials, name=member.name, color=member.color)


def member_out(member: TeamMember) -> MemberOut:
    return MemberOut.model_validate(member)


def labels_out(names: list[str] | None) -> list[LabelOut]:
    return [LabelOut(name=n, color=label_color(n)) for n in (names or [])]


def pr_out(pr: PullRequest | None) -> PullRequestOut | None:
    if pr is None:
        return None
    return PullRequestOut(
        num=pr.num,
        title=pr.title,
        branch=pr.branch,
        state=pr.state,
        checks=pr.checks,
        additions=pr.additions,
        deletions=pr.deletions,
        files_changed=pr.files_changed,
        ai_generated=pr.ai_generated,
        reviewers=[
            ReviewerOut(member=member_ref(r.member), state=r.state) for r in pr.reviewers
        ],
    )


def feature_ref(feature: Issue | None) -> FeatureRef | None:
    if feature is None:
        return None
    return FeatureRef(key=feature.key, title=feature.title, color=feature.color)


def issue_out(issue: Issue) -> IssueOut:
    return IssueOut(
        key=issue.key,
        type=issue.type,
        title=issue.title,
        priority=issue.priority,
        status=issue.status,
        space=issue.space,
        points=issue.points,
        assignee=member_ref(issue.assignee),
        owner=member_ref(issue.owner),
        feature=feature_ref(issue.feature),
        sprint=issue.sprint_id,
        labels=labels_out(issue.labels),
        branch=issue.branch,
        blocked=issue.blocked,
        review_requested=issue.review_requested,
        comment_count=issue.comment_count,
        pr=pr_out(issue.pr),
        product=issue.product,
        component=issue.component,
        task_id=issue.task_id,
        target_release=issue.target_release or [],
        monday_item_id=issue.monday_item_id,
        monday_board_id=issue.monday_board_id,
        monday_synced_at=issue.monday_synced_at,
        sync_state=_sync_state(issue),
        monday_status=issue.monday_status,
        monday_status_color=issue.monday_status_color,
    )


def _sync_state(issue: Issue) -> str | None:
    """'synced' once monday has the latest, 'pending' when a local change hasn't
    reached monday yet, None when the ticket isn't linked to monday at all."""
    if not issue.monday_item_id:
        return None
    return "synced" if issue.monday_synced_at is not None else "pending"


# Synthetic author for AI-authored comments (no real team member needed).
_AI_AUTHOR = MemberRef(initials="AI", name="risr/crm AI", color="#8B5CF6")


def comment_out(comment: Comment) -> CommentOut:
    author = _AI_AUTHOR if comment.kind == "ai" else member_ref(comment.author)
    return CommentOut(
        id=comment.id,
        author=author,
        kind=comment.kind,
        body=comment.body,
        created_at=comment.created_at,
    )


_HEADING_RE = re.compile(r"^#{1,6}\s+(.*)$")
_BULLET_RE = re.compile(r"^[-*]\s+(.*)$")
_IMAGE_RE = re.compile(r"^!\[([^\]]*)\]\(([^)]+)\)$")
_LINK_RE = re.compile(r"^\[([^\]]+)\]\(([^)]+)\)$")


def description_blocks(text: str | None) -> list[DescriptionBlock]:
    """Parse a light markdown string into heading/paragraph/list blocks."""
    if not text:
        return []
    blocks: list[DescriptionBlock] = []
    pending_list: list[str] = []

    def flush_list() -> None:
        if pending_list:
            blocks.append(DescriptionBlock(type="list", items=list(pending_list)))
            pending_list.clear()

    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            flush_list()
            continue
        if (m := _IMAGE_RE.match(line)):
            flush_list()
            blocks.append(DescriptionBlock(type="image", text=m.group(1) or None, url=m.group(2)))
        elif (m := _LINK_RE.match(line)):
            flush_list()
            blocks.append(DescriptionBlock(type="link", text=m.group(1), url=m.group(2)))
        elif (m := _HEADING_RE.match(line)):
            flush_list()
            blocks.append(DescriptionBlock(type="heading", text=m.group(1)))
        elif (m := _BULLET_RE.match(line)):
            pending_list.append(m.group(1))
        else:
            flush_list()
            blocks.append(DescriptionBlock(type="paragraph", text=line))
    flush_list()
    return blocks


def child_progress(children: list[Issue]) -> ChildProgress:
    total = sum(c.points for c in children)
    done = sum(c.points for c in children if c.status == DONE)
    return ChildProgress(done=done, total=total)


def audit_out(a) -> AuditEntryOut:
    return AuditEntryOut(
        id=a.id, actor=member_ref(a.actor), summary=a.summary, created_at=a.created_at
    )


def issue_detail(issue: Issue) -> IssueDetailOut:
    base = issue_out(issue)
    detail = IssueDetailOut(
        **base.model_dump(by_alias=False),
        description=description_blocks(issue.description),
        comments=[comment_out(c) for c in issue.comments],
        prs=[pr_out(p) for p in issue.prs],
        audit_log=[audit_out(a) for a in issue.audit_logs],
        monday_fields=[
            MondayFieldOut(
                title=f.get("title", ""),
                value=f.get("text", ""),
                type=f.get("type"),
                color=f.get("color"),
            )
            for f in (issue.monday_fields or [])
        ],
    )
    if issue.type == IssueType.epic:
        kids = sorted(issue.children, key=lambda c: c.key)
        detail.children = [issue_out(c) for c in kids]
        detail.child_progress = child_progress(kids)
    return detail
