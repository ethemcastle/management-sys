"""Seed the database from seed_data.json (verbatim), plus deterministic
synthesis of reviewers, activity (comments/commits), and descriptions so the
detail pages are fully populated. Idempotent: only seeds an empty database.
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import settings
from app.db import Base, SessionLocal, engine
from app.models.calendar import CalendarAccount
from app.models.comment import Comment
from app.models.email import Email, IgnoreRule
from app.models.github import GitHubRepo
from app.models.enums import (
    CiStatus,
    EmailCategory,
    IgnoreField,
    IssueType,
    PrState,
    ReviewState,
    Space,
    Status,
)
from app.models.issue import Issue
from app.models.member import TeamMember
from app.models.monday import MondayAccount
from app.models.pull_request import PullRequest
from app.models.recap import MeetingNote
from app.models.ybug import YbugAccount
from app.models.zoom import ZoomAccount
from app.models.reviewer import Reviewer
from app.models.sprint import Sprint

PRIORITY_LABELS = ["Low", "Medium", "High", "Urgent"]
_BASE_TIME = datetime(2026, 7, 8, 9, 0, tzinfo=timezone.utc)

_COMMENT_POOL = [
    "Started digging in — root cause looks like a missing guard on the edge case.",
    "Pushed a first pass; tests are green locally.",
    "Left a couple of notes on the PR, mostly naming and one null-check.",
    "Confirmed the repro on staging, attaching steps.",
    "Rebased on main to pick up the latest fixes.",
    "Good catch — updated the approach and added a regression test.",
    "This is ready for another look when you get a sec.",
    "Nit addressed; squashing before merge.",
    "Verified the fix end-to-end, no more duplicates.",
]


def load_seed() -> dict:
    with settings.seed_data_path.open(encoding="utf-8") as fh:
        return json.load(fh)


def _make_description(d: dict, feature_title: str | None) -> str:
    title = d["title"]
    labels = ", ".join(d.get("labels") or []) or "general"
    prio = PRIORITY_LABELS[d.get("priority", 1)]
    feature_clause = f" under **{feature_title}**" if feature_title else ""
    return (
        f"## Context\n"
        f"{title}. This work sits in the {d['space']} track{feature_clause}.\n\n"
        f"## Acceptance criteria\n"
        f"- The behavior in the title is implemented and covered by tests.\n"
        f"- No regressions in related areas ({labels}).\n"
        f"- CI is green and the change has a review approval.\n\n"
        f"## Notes\n"
        f"Tracked as {d['key']} — {d['type']}, {d.get('points', 0)} pts, priority {prio}."
    )


def _synthesize_comments(issue: Issue, members: dict[str, TeamMember]) -> list[Comment]:
    count = issue.comment_count
    if count <= 0:
        return []
    # rotate through the assignee and a couple of teammates for authorship
    order = [i for i in (issue.assignee_initials, "MP", "AL", "JC", "SL") if i in members]
    if not order:
        order = list(members)[:3]
    out: list[Comment] = []
    for n in range(count):
        author = order[n % len(order)]
        created = _BASE_TIME - timedelta(hours=(count - n) * 5)
        if issue.branch and n == count - 1:
            out.append(
                Comment(
                    issue_key=issue.key,
                    author_initials=author,
                    kind="commit",
                    body=f"pushed 3 commits to {issue.branch}",
                    created_at=created,
                )
            )
        else:
            out.append(
                Comment(
                    issue_key=issue.key,
                    author_initials=author,
                    kind="comment",
                    body=_COMMENT_POOL[(hash(issue.key) + n) % len(_COMMENT_POOL)],
                    created_at=created,
                )
            )
    return out


def _synthesize_reviewers(
    issue: Issue, pr: PullRequest, members: dict[str, TeamMember], current: str
) -> list[Reviewer]:
    reviewers: list[Reviewer] = []
    used: set[str] = {issue.assignee_initials or ""}

    # Put the current user on the review when a review was explicitly requested,
    # so the developer dashboard's "Review requests" card is populated.
    if issue.review_requested and issue.assignee_initials != current:
        reviewers.append(Reviewer(pr_num=pr.num, member_initials=current, state=ReviewState.pending))
        used.add(current)

    # A secondary reviewer with a state that reflects PR/CI health, for variety.
    candidates = [m for m in members if m not in used and members[m].role == "developer"]
    if candidates:
        sec = candidates[pr.num % len(candidates)]
        if pr.state == PrState.merged:
            state = ReviewState.approved
        elif pr.checks == CiStatus.failing:
            state = ReviewState.changes
        else:
            state = [ReviewState.approved, ReviewState.pending, ReviewState.changes][pr.num % 3]
        reviewers.append(Reviewer(pr_num=pr.num, member_initials=sec, state=state))
    return reviewers


# (sender_name, email, color, subject, preview, category, labels, hours_ago, unread, starred)
_EMAILS: list[tuple] = [
    ("Priya Nandan", "priya@acme-corp.com", "#0E7C86",
     "Can't export CSV over 10k rows",
     "Hi team — our weekly export keeps failing when the report goes past ~10k rows. This is blocking our Monday review.",
     EmailCategory.customer, ["support"], 1, True, True),
    ("Marcus Webb", "marcus@globex.io", "#B45AF2",
     "SSO login loop on Okta",
     "We're seeing users bounced back to the login page when signing in with Okta. Started this morning.",
     EmailCategory.customer, ["support", "urgent"], 3, True, False),
    ("Dana Cole", "dana@brightpath.co", "#E8833A",
     "Feature request: saved filters",
     "Love the product! One thing that would really help our team is saving and sharing board filters.",
     EmailCategory.customer, [], 26, False, False),
    ("Aria Rahman", "aria@northwind.example", "#E8833A",
     "Re: onboarding stepper review",
     "Pushed the latest — can you take another look at the stepper spacing on CAD-142 when you get a sec?",
     EmailCategory.internal, ["design"], 2, True, False),
    ("Mira Patel", "mira@northwind.example", "#5A50E1",
     "Sprint 24 scope check",
     "We added CAD-160 mid-sprint; flagging for capacity. Can we talk at the mid-sprint check-in?",
     EmailCategory.internal, [], 5, True, False),
    ("Jonas Cole", "jonas@northwind.example", "#2E9E5B",
     "Billing webhook postmortem notes",
     "Draft notes attached ahead of tomorrow's postmortem. Root cause looks like a missing idempotency key.",
     EmailCategory.internal, [], 20, False, False),
    ("GitHub", "notifications@github.com", "#57606A",
     "[cadence] PR #814 checks failing",
     "The build failed on fix/billing-webhook. 1 of 3 checks failed — see the run for details.",
     EmailCategory.notification, ["github"], 2, True, False),
    ("risr/crm CI", "ci@cadence.dev", "#3B7DD8",
     "Deploy to staging succeeded",
     "Build 4821 deployed to staging in 3m 12s. All smoke tests passed.",
     EmailCategory.notification, ["ci"], 6, False, False),
    ("GitHub", "notifications@github.com", "#57606A",
     "SL requested changes on #812",
     "Sena Liu requested changes on your pull request 'Redesign onboarding checklist stepper'.",
     EmailCategory.notification, ["github"], 22, False, False),
    ("Frontend Weekly", "hello@frontendweekly.co", "#C0A227",
     "Signals everywhere: an Angular deep dive",
     "This week: zoneless change detection, the new control flow, and patterns for signal stores.",
     EmailCategory.newsletter, [], 9, False, False),
    ("TLDR", "newsletter@tldr.tech", "#95948B",
     "TLDR: the week in tech",
     "Top stories: a new open model, a big acquisition, and five tools worth a look.",
     EmailCategory.newsletter, [], 30, False, False),
    ("Stripe Billing", "alerts@stripe.com", "#635BFF",
     "Failed payment retries spiking",
     "We retried 3 invoices that failed in the last hour. You may want to check the billing webhook.",
     EmailCategory.alert, ["billing"], 1, True, False),
    ("PagerDuty", "noreply@pagerduty.com", "#06AC38",
     "Resolved: elevated 500s on /login",
     "Incident #4471 auto-resolved after 12 minutes. No further action required.",
     EmailCategory.alert, ["oncall"], 12, False, False),
    ("Google Calendar", "calendar-notification@google.com", "#8B5CF6",
     "Invitation: Realtime sync architecture",
     "Thursday 1:00pm · You've been invited by Sena Liu. Google Meet link included.",
     EmailCategory.meeting, [], 4, True, False),
]


def _seed_inbox(db: Session, members: dict[str, TeamMember]) -> None:
    now = datetime.now(timezone.utc)
    for (name, email, color, subject, preview, category, labels, hours, unread, starred) in _EMAILS:
        db.add(
            Email(
                sender_name=name,
                sender_email=email,
                sender_color=color,
                subject=subject,
                preview=preview,
                body=f"{preview}\n\nThanks,\n{name}",
                category=category,
                labels=labels,
                received_at=now - timedelta(hours=hours),
                unread=unread,
                starred=starred,
            )
        )
    # One example ignore rule so the recap/ignore behavior is visible out of the box.
    db.add(IgnoreRule(field=IgnoreField.category, value="newsletter", active=True))


def _seed_calendar(db: Session) -> None:
    # Start disconnected; the user connects (mock Google) to import the week.
    if db.scalar(select(func.count()).select_from(CalendarAccount)) == 0:
        db.add(CalendarAccount(connected=False))


def _seed_github(db: Session) -> None:
    # Start disconnected; connecting imports the branch/PR pool (mock GitHub).
    if db.scalar(select(func.count()).select_from(GitHubRepo)) == 0:
        db.add(GitHubRepo(connected=False))


def _seed_monday(db: Session) -> None:
    # Start disconnected; connecting imports the boards/items (mock monday.com).
    if db.scalar(select(func.count()).select_from(MondayAccount)) == 0:
        db.add(MondayAccount(connected=False))


def _seed_zoom(db: Session) -> None:
    # Start disconnected; connecting enables Zoom AI Companion recaps (mock).
    if db.scalar(select(func.count()).select_from(ZoomAccount)) == 0:
        db.add(ZoomAccount(connected=False))


def _seed_ybug(db: Session) -> None:
    # Start disconnected; connecting turns Ybug feedback into board tickets (mock).
    if db.scalar(select(func.count()).select_from(YbugAccount)) == 0:
        db.add(YbugAccount(connected=False))


def seed_database(db: Session) -> None:
    data = load_seed()
    current = data.get("currentUser", "AL")

    members: dict[str, TeamMember] = {}
    for m in data["teamMembers"]:
        member = TeamMember(
            initials=m["initials"],
            name=m["name"],
            color=m["color"],
            role=m["role"],
            is_current_user=bool(m.get("isCurrentUser", False)),
        )
        members[member.initials] = member
        db.add(member)

    for s in data["sprints"]:
        db.add(
            Sprint(
                id=s["id"],
                name=s["name"],
                range=s["range"],
                goal=s.get("goal", ""),
                days_left=s.get("daysLeft"),
                days_total=s.get("daysTotal", 10),
                capacity=s.get("capacity"),
                active=bool(s.get("active", False)),
            )
        )

    # Features (epics) first — child issues FK to their key.
    feature_titles: dict[str, str] = {}
    for f in data["features"]:
        feature_titles[f["key"]] = f["title"]
        db.add(
            Issue(
                key=f["key"],
                type=IssueType.epic,
                title=f["title"],
                priority=f.get("priority", 1),
                status=Status(f.get("status", "inprogress")),
                space=Space(f["space"]),
                points=0,
                assignee_initials=f.get("assignee"),
                color=f.get("color"),
                labels=[],
                comment_count=0,
                description=(
                    f"## Feature\n{f['title']} — a parent work item grouping the tasks below."
                ),
            )
        )
    db.flush()

    # Child / standalone issues (+ PRs, reviewers, comments, descriptions).
    for d in data["issues"]:
        issue = Issue(
            key=d["key"],
            type=IssueType(d["type"]),
            title=d["title"],
            priority=d.get("priority", 1),
            status=Status(d["status"]),
            space=Space(d["space"]),
            points=d.get("points", 0),
            assignee_initials=d.get("assignee"),
            feature_key=d.get("feature"),
            sprint_id=d.get("sprint"),
            branch=d.get("branch"),
            blocked=bool(d.get("blocked", False)),
            review_requested=bool(d.get("reviewRequested", False)),
            labels=d.get("labels", []),
            comment_count=d.get("comments", 0),
            description=_make_description(d, feature_titles.get(d.get("feature") or "")),
        )
        db.add(issue)
        db.flush()

        pr_data = d.get("pr")
        if pr_data:
            pr = PullRequest(
                num=pr_data["num"],
                issue_key=issue.key,
                title=pr_data.get("title", issue.title),
                branch=d.get("branch") or pr_data.get("branch"),
                state=PrState(pr_data["state"]),
                checks=CiStatus(pr_data["checks"]),
                additions=pr_data.get("additions", 120),
                deletions=pr_data.get("deletions", 34),
                files_changed=pr_data.get("filesChanged", 5),
                ai_generated=bool(pr_data.get("aiGenerated", False)),
            )
            db.add(pr)
            db.flush()
            for rev in _synthesize_reviewers(issue, pr, members, current):
                db.add(rev)

        for comment in _synthesize_comments(issue, members):
            db.add(comment)

    _seed_inbox(db, members)
    _seed_calendar(db)
    _seed_github(db)
    _seed_monday(db)
    _seed_zoom(db)
    _seed_ybug(db)
    db.commit()


def database_is_empty(db: Session) -> bool:
    return db.scalar(select(func.count()).select_from(TeamMember)) == 0


def _ensure_columns() -> None:
    """Add newer nullable columns to existing tables — `create_all` creates missing
    tables but never alters existing ones. SQLite ADD COLUMN is safe and idempotent;
    preserves all existing data (no drop/reseed needed)."""
    if not settings.database_url.startswith("sqlite"):
        return  # non-sqlite: manage via a real migration
    wanted = {
        "issues": {
            "owner_initials": "VARCHAR",
            "product": "VARCHAR(80)",
            "component": "VARCHAR(80)",
            "task_id": "VARCHAR(48)",
            "target_release": "JSON",
            "monday_item_id": "VARCHAR(48)",
            "monday_board_id": "VARCHAR(48)",
            "monday_synced_at": "DATETIME",
            "monday_status": "VARCHAR(80)",
            "monday_status_color": "VARCHAR(9)",
            "monday_fields": "JSON",
        },
        "repo_pull_requests": {"checks_detail": "JSON"},
        "monday_boards": {"url": "VARCHAR(400)", "columns_meta": "JSON", "groups": "JSON"},
        "monday_items": {"columns": "JSON"},
        "meeting_recaps": {"source": "VARCHAR(24)"},
    }
    with engine.begin() as conn:
        for table, cols in wanted.items():
            existing = {row[1] for row in conn.exec_driver_sql(f"PRAGMA table_info({table})")}
            for col, coltype in cols.items():
                if col not in existing:
                    conn.exec_driver_sql(f"ALTER TABLE {table} ADD COLUMN {col} {coltype}")


def _seed_catalog() -> None:
    """Populate the catalog with the distinct Product/Component values already on
    issues (so the Settings page reflects current data). Idempotent; runs each start."""
    from app.models.catalog import CatalogItem
    from app.models.issue import Issue

    with SessionLocal() as db:
        have = {(c.kind, c.name.lower()) for c in db.scalars(select(CatalogItem))}

        def ensure(kind: str, name: str | None) -> None:
            if name and name.strip() and (kind, name.lower()) not in have:
                db.add(CatalogItem(kind=kind, name=name.strip()))
                have.add((kind, name.lower()))

        for col, kind in ((Issue.product, "product"), (Issue.component, "component")):
            for (val,) in db.execute(
                select(col).where(col.is_not(None), col != "").distinct()
            ):
                ensure(kind, val)
        db.commit()


def _ensure_task_ids() -> None:
    """Backfill auto-generated, unique external Task IDs (e.g. RISR-0001) for any
    issue missing one. Idempotent; keeps the running counter above existing ids."""
    import re

    from app.models.issue import Issue

    prefix = settings.task_id_prefix
    with SessionLocal() as db:
        existing = db.scalars(select(Issue.task_id).where(Issue.task_id.like(f"{prefix}-%"))).all()
        nums = [int(m.group(1)) for t in existing if t and (m := re.match(rf"{prefix}-(\d+)$", t))]
        n = max(nums) if nums else 0
        missing = db.scalars(
            select(Issue)
            .where((Issue.task_id.is_(None)) | (Issue.task_id == ""))
            .order_by(Issue.key)
        ).all()
        for issue in missing:
            n += 1
            issue.task_id = f"{prefix}-{n:04d}"
        if missing:
            db.commit()


def seed_if_empty() -> None:
    Base.metadata.create_all(bind=engine)
    _ensure_columns()
    with SessionLocal() as db:
        if database_is_empty(db):
            seed_database(db)
    _seed_catalog()
    _ensure_task_ids()


def reset_and_seed() -> None:
    """Drop everything and reseed — handy for local dev."""
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    with SessionLocal() as db:
        seed_database(db)


if __name__ == "__main__":
    reset_and_seed()
    print("Seeded risr/crm database at", settings.database_url)
