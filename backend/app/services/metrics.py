"""Server-side computations: board grouping, sprint health, backlog groups,
reports, timeline, and the role dashboards. The UI renders these numbers
directly, so all the business rules live here (not in the client).
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.enums import CiStatus, IssueType, ReviewState, Role, Space, Status
from app.models.issue import Issue
from app.models.member import TeamMember
from app.models.sprint import Sprint
from app.schemas.entities import MemberRef
from app.schemas.views import (
    ActionItem,
    BacklogGroup,
    BacklogOut,
    BoardColumn,
    BoardOut,
    Burndown,
    DashboardDeveloper,
    DashboardPo,
    MondaySummary,
    DistributionSlice,
    EpicProgressRow,
    ReportsOut,
    RiskItem,
    SprintHealthOut,
    StatCard,
    TimelineMonth,
    TimelineOut,
    TimelineRow,
    VelocityBar,
    WorkloadRow,
)
from app.services import serializers as S

# --- board configuration ----------------------------------------------------
BOARD_ORDER: list[Status] = [Status.todo, Status.inprogress, Status.review, Status.done]
COLUMN_TITLES: dict[Status, str] = {
    Status.todo: "To Do",
    Status.inprogress: "In Progress",
    Status.review: "In Review",
    Status.done: "Done",
}
WIP_LIMITS: dict[Status, int] = {
    Status.todo: 6,
    Status.inprogress: 4,
    Status.review: 3,
    Status.done: 0,  # 0 == no limit
}
OVERLOAD_POINTS = 13  # a member at/over this is flagged red in workload


# --- shared queries ---------------------------------------------------------
def non_epic_issues(db: Session, space: Space) -> list[Issue]:
    stmt = select(Issue).where(Issue.space == space, Issue.type != IssueType.epic)
    return list(db.scalars(stmt))


def epics(db: Session, space: Space) -> list[Issue]:
    stmt = (
        select(Issue)
        .where(Issue.space == space, Issue.type == IssueType.epic)
        .order_by(Issue.key)
    )
    return list(db.scalars(stmt))


def active_sprint(db: Session) -> Sprint | None:
    return db.scalars(select(Sprint).where(Sprint.active.is_(True))).first()


def sprint_issues(db: Session, space: Space, sprint_id: str) -> list[Issue]:
    return [i for i in non_epic_issues(db, space) if i.sprint_id == sprint_id]


# --- board ------------------------------------------------------------------
def build_board(db: Session, space: Space, sprint_id: str | None) -> BoardOut:
    issues = non_epic_issues(db, space)
    if sprint_id:
        issues = [i for i in issues if i.sprint_id == sprint_id]
    columns: list[BoardColumn] = []
    for status in BOARD_ORDER:
        col_issues = [S.issue_out(i) for i in issues if i.status == status]
        col_issues.sort(key=lambda x: (-x.priority, x.key))
        columns.append(
            BoardColumn(
                key=status,
                title=COLUMN_TITLES[status],
                wip_limit=WIP_LIMITS[status],
                count=len(col_issues),
                issues=col_issues,
            )
        )
    return BoardOut(columns=columns)


# --- sprint health ----------------------------------------------------------
def sprint_health(db: Session, space: Space, sprint_id: str | None) -> SprintHealthOut:
    sprint = db.get(Sprint, sprint_id) if sprint_id else active_sprint(db)
    if space == Space.support or sprint is None:
        issues = [i for i in non_epic_issues(db, space) if i.sprint_id == (sprint.id if sprint else None)]
        capacity = sprint.capacity if sprint else None
    else:
        issues = sprint_issues(db, space, sprint.id)
        capacity = sprint.capacity

    def pts(status: Status) -> int:
        return sum(i.points for i in issues if i.status == status)

    total = sum(i.points for i in issues)
    done = pts(Status.done)
    in_progress = pts(Status.inprogress)
    review = pts(Status.review)
    todo = pts(Status.todo) + pts(Status.backlog)
    committed = capacity if capacity is not None else total
    remaining = total - done
    scope_added = max(0, total - committed)
    on_track = remaining <= (committed if committed else total)
    return SprintHealthOut(
        committed=committed,
        done=done,
        in_progress=in_progress,
        review=review,
        todo=todo,
        remaining=remaining,
        scope_added=scope_added,
        on_track=on_track,
    )


# --- backlog ----------------------------------------------------------------
def _group(id_: str, name: str, issues: list[Issue], **kw) -> BacklogGroup:
    outs = [S.issue_out(i) for i in sorted(issues, key=lambda x: (-x.priority, x.key))]
    return BacklogGroup(
        id=id_,
        name=name,
        points=sum(i.points for i in issues),
        count=len(issues),
        issues=outs,
        **kw,
    )


def build_backlog(db: Session, space: Space) -> BacklogOut:
    issues = non_epic_issues(db, space)
    if space == Space.features:
        sprints = list(db.scalars(select(Sprint).order_by(Sprint.id)))
        active = next((s for s in sprints if s.active), None)
        planning = next((s for s in sprints if not s.active), None)
        groups: list[BacklogGroup] = []
        if active:
            in_active = [i for i in issues if i.sprint_id == active.id]
            groups.append(
                _group(
                    active.id,
                    active.name,
                    in_active,
                    meta=f"{active.days_left} days left · {active.range}"
                    if active.days_left is not None
                    else active.range,
                    active=True,
                    capacity=active.capacity,
                )
            )
        if planning:
            in_planning = [i for i in issues if i.sprint_id == planning.id]
            groups.append(
                _group(
                    planning.id,
                    planning.name,
                    in_planning,
                    meta=f"Planning · {planning.range}",
                    capacity=planning.capacity,
                )
            )
        unscheduled = [i for i in issues if i.sprint_id is None]
        groups.append(_group("backlog", "Backlog", unscheduled, meta="Unscheduled"))
        return BacklogOut(groups=groups)

    # support space: triage-style buckets
    triage = [i for i in issues if i.status in (Status.todo, Status.backlog)]
    working = [i for i in issues if i.status in (Status.inprogress, Status.review)]
    resolved = [i for i in issues if i.status == Status.done]
    return BacklogOut(
        groups=[
            _group("triage", "Needs triage", triage, meta="Awaiting first response"),
            _group("working", "Being worked", working, meta="In progress or review"),
            _group("resolved", "Resolved", resolved, meta="Closed this week"),
        ]
    )


# --- reports ----------------------------------------------------------------
# The four headline stat cards are curated presentation values (see 05_SCREENS).
_STAT_CARDS = [
    StatCard(label="Avg cycle time", value="2.4", unit="days", delta="−0.3d", good=True),
    StatCard(label="Throughput", value="18", unit="issues/sprint", delta="+2", good=True),
    StatCard(label="PRs merged", value="6", unit="this sprint", delta="+1", good=True),
    StatCard(label="Avg review time", value="5.2", unit="hours", delta="−0.8h", good=True),
]


def build_reports(db: Session, space: Space, sprint_id: str | None) -> ReportsOut:
    health = sprint_health(db, space, sprint_id)
    total = health.committed or (health.done + health.review + health.in_progress + health.todo)
    max_pts = max(total, 1)

    # burndown: ideal is a straight line to zero; actual trails slightly behind
    # for the elapsed portion of the sprint.
    sprint = db.get(Sprint, sprint_id) if sprint_id else active_sprint(db)
    days_total = sprint.days_total if sprint else 10
    days_left = sprint.days_left if (sprint and sprint.days_left is not None) else days_total
    elapsed = max(0, days_total - days_left)
    ideal = [round(max_pts * (1 - i / days_total), 1) for i in range(days_total + 1)]
    # actual trails from the full commitment down to the current remaining over
    # the elapsed days (slightly behind the ideal line for realism).
    actual: list[float] = []
    for i in range(elapsed + 1):
        if elapsed == 0:
            actual.append(float(max_pts))
        else:
            actual.append(round(max_pts - (max_pts - health.remaining) * (i / elapsed), 1))
    burndown = Burndown(max=max_pts, ideal=ideal, actual=actual, days=["Jul 1", "Jul 8", "Jul 14"])

    # velocity: a 5-sprint history ending at the current sprint.
    velocity = [
        VelocityBar(sprint="S20", committed=38, completed=40),
        VelocityBar(sprint="S21", committed=42, completed=39),
        VelocityBar(sprint="S22", committed=40, completed=42),
        VelocityBar(sprint="S23", committed=44, completed=41),
        VelocityBar(sprint="S24", committed=health.committed, completed=health.done),
    ]

    # distribution: issue counts by board status in the active sprint.
    issues = sprint_issues(db, space, sprint.id) if (sprint and space == Space.features) else non_epic_issues(db, space)
    dist_defs = [
        (Status.todo, "To Do"),
        (Status.inprogress, "In Progress"),
        (Status.review, "In Review"),
        (Status.done, "Done"),
    ]
    distribution = [
        DistributionSlice(status=st, label=lbl, count=sum(1 for i in issues if i.status == st))
        for st, lbl in dist_defs
    ]
    return ReportsOut(stats=_STAT_CARDS, burndown=burndown, velocity=velocity, distribution=distribution)


# --- timeline ---------------------------------------------------------------
# Deterministic roadmap placement per feature (weeks are 1-indexed over a
# 12-week, 3-month grid). Progress comes from the epic's children.
_ROADMAP: dict[str, tuple[int, int]] = {
    "CAD-100": (1, 4),
    "CAD-120": (1, 5),
    "CAD-105": (2, 5),
    "CAD-130": (4, 6),
    "CAD-135": (6, 4),
    "CAD-190": (8, 5),
}


def build_timeline(db: Session, space: Space) -> TimelineOut:
    if space != Space.features:
        return TimelineOut(months=[], today_week=1, rows=[])
    rows: list[TimelineRow] = []
    for idx, feature in enumerate(epics(db, space)):
        prog = _epic_progress(feature)
        start, span = _ROADMAP.get(feature.key, (1 + idx, 4))
        rows.append(
            TimelineRow(
                feature_key=feature.key,
                name=feature.title,
                color=feature.color or "#5A50E1",
                start_week=start,
                span_weeks=span,
                progress=prog.progress,
            )
        )
    months = [
        TimelineMonth(label="July", start_week=1, span_weeks=4),
        TimelineMonth(label="August", start_week=5, span_weeks=4),
        TimelineMonth(label="September", start_week=9, span_weeks=4),
    ]
    return TimelineOut(months=months, today_week=1, rows=rows)


# --- dashboards -------------------------------------------------------------
class _EpicProg:
    __slots__ = ("done", "total", "progress")

    def __init__(self, done: int, total: int) -> None:
        self.done = done
        self.total = total
        self.progress = round(done / total, 3) if total else 0.0


def _epic_progress(feature: Issue) -> _EpicProg:
    kids = feature.children
    total = sum(k.points for k in kids)
    done = sum(k.points for k in kids if k.status == Status.done)
    return _EpicProg(done, total)


def current_user(db: Session) -> TeamMember:
    user = db.scalars(select(TeamMember).where(TeamMember.is_current_user.is_(True))).first()
    if user is None:  # pragma: no cover - seed guarantees one
        user = db.scalars(select(TeamMember)).first()
    return user


def build_dashboard_developer(db: Session, space: Space) -> DashboardDeveloper:
    me = current_user(db)
    issues = non_epic_issues(db, space)
    my_focus = [i for i in issues if i.assignee_initials == me.initials and i.status != Status.done]
    my_focus.sort(key=lambda i: (-i.priority, i.key))

    review_queue = [
        i
        for i in issues
        if i.pr is not None
        and i.assignee_initials != me.initials
        and any(r.member_initials == me.initials for r in i.pr.reviewers)
    ]
    my_prs = [i for i in issues if i.assignee_initials == me.initials and i.pr is not None]

    standup = _standup_bullets(my_focus, my_prs, review_queue)

    # --- "Needs you" ranked action queue (deduped by key, highest severity wins) ---
    actions: list[ActionItem] = []
    seen: set[str] = set()

    def add(issue: Issue, kind: str, reason: str, severity: int) -> None:
        if issue.key in seen:
            return
        seen.add(issue.key)
        actions.append(ActionItem(kind=kind, issue=S.issue_out(issue), reason=reason, severity=severity))

    mine_or_reviewing = (
        {i.key for i in my_focus} | {i.key for i in review_queue} | {i.key for i in my_prs}
    )
    # 1) CI failing on a PR I own or review
    failing_ci = [
        i for i in issues
        if i.pr is not None and i.pr.checks == CiStatus.failing and i.key in mine_or_reviewing
    ]
    for i in failing_ci:
        add(i, "ci_failing", f"CI failing on #{i.pr.num}", 100)
    # 2) changes requested (on my review, or on a PR I own)
    for i in issues:
        if i.pr is None:
            continue
        mine_pr = i.assignee_initials == me.initials
        changed = any(
            r.state == ReviewState.changes and (mine_pr or r.member_initials == me.initials)
            for r in i.pr.reviewers
        )
        if changed and (mine_pr or any(r.member_initials == me.initials for r in i.pr.reviewers)):
            add(i, "changes_requested", f"Changes requested on #{i.pr.num}", 80)
    # 3) review requests waiting on me
    for i in review_queue:
        who = i.assignee.name if i.assignee else "a teammate"
        add(i, "review_request", f"Review requested by {who}", 60)
    # 4) blocked & mine
    blocked = [i for i in my_focus if i.blocked]
    for i in blocked:
        add(i, "blocked", "Blocked — needs unblocking", 50)
    # 5) monday changes not yet pushed (mine)
    unsynced = [
        i for i in issues
        if i.monday_item_id and i.monday_synced_at is None and i.assignee_initials == me.initials
    ]
    for i in unsynced:
        add(i, "monday_unsynced", f"Pending sync to monday · {i.monday_status or 'monday'}", 30)

    actions.sort(key=lambda a: -a.severity)
    last_synced = max(
        (i.monday_synced_at for i in issues if i.monday_synced_at is not None),
        default=None,
    )

    return DashboardDeveloper(
        my_focus=[S.issue_out(i) for i in my_focus],
        review_queue=[S.issue_out(i) for i in review_queue],
        my_prs=[S.issue_out(i) for i in my_prs],
        standup=standup,
        sprint_health=sprint_health(db, space, None),
        action_items=actions,
        blocked=[S.issue_out(i) for i in blocked],
        failing_ci=[S.issue_out(i) for i in failing_ci],
        monday=MondaySummary(pending_count=len(unsynced), last_synced_at=last_synced),
    )


def _standup_bullets(my_focus, my_prs, review_queue) -> list[str]:
    focus = my_focus[0].title if my_focus else "sprint tasks"
    prs = ", ".join(f"#{i.pr.num}" for i in my_prs if i.pr) or "no open PRs"
    return [
        f"Yesterday: pushed progress on {focus} and kept CI green.",
        f"Today: focus on {len(my_focus)} assigned item(s); primary is “{focus}”.",
        f"PRs: {prs}. {len(review_queue)} review request(s) waiting on you.",
        "Blockers: none — flag early if the auth-cookie migration slips.",
    ]


def build_dashboard_po(db: Session, space: Space) -> DashboardPo:
    health = sprint_health(db, space, None)
    issues = non_epic_issues(db, space)
    sprint = active_sprint(db)
    in_sprint = [i for i in issues if (sprint is None or i.sprint_id == sprint.id)]

    # risks — rule-based, one reason per issue, de-duplicated
    risks: list[RiskItem] = []
    seen: set[str] = set()

    def add(issue: Issue, reason: str) -> None:
        if issue.key not in seen:
            seen.add(issue.key)
            risks.append(RiskItem(issue=S.issue_out(issue), reason=reason))

    for i in in_sprint:
        if i.pr and i.pr.checks == CiStatus.failing:
            add(i, "CI failing")
    for i in in_sprint:
        if i.blocked:
            add(i, "Blocked · unstarted")
    for i in in_sprint:
        if i.points >= 8 and i.status not in (Status.done, Status.review):
            add(i, "Large · at risk")
    for i in in_sprint:
        if i.status == Status.review and i.review_requested:
            add(i, "Awaiting review 2d")

    # workload — open (non-done) points per member
    members = list(db.scalars(select(TeamMember)))
    workload: list[WorkloadRow] = []
    for m in members:
        pts = sum(
            i.points for i in issues if i.assignee_initials == m.initials and i.status != Status.done
        )
        if pts > 0:
            workload.append(
                WorkloadRow(
                    member=MemberRef(initials=m.initials, name=m.name, color=m.color),
                    points=pts,
                    overloaded=pts >= OVERLOAD_POINTS,
                )
            )
    workload.sort(key=lambda w: -w.points)

    epic_rows: list[EpicProgressRow] = []
    for feature in epics(db, space):
        prog = _epic_progress(feature)
        epic_rows.append(
            EpicProgressRow(
                key=feature.key,
                title=feature.title,
                color=feature.color or "#5A50E1",
                done=prog.done,
                total=prog.total,
                progress=prog.progress,
            )
        )

    return DashboardPo(
        sprint_health=health,
        risks=risks[:5],
        workload=workload,
        epic_progress=epic_rows,
        weekly_report=_weekly_report(health, risks),
    )


def _weekly_report(health: SprintHealthOut, risks: list[RiskItem]) -> str:
    return (
        f"Sprint 24 is {'on track' if health.on_track else 'at risk'}: "
        f"{health.done} of {health.committed} committed points are done with "
        f"{health.remaining} remaining and {health.in_progress} in progress. "
        f"{len(risks)} item(s) need attention — chiefly CI failures on billing and the "
        f"blocked auth-cookie migration. Onboarding v2 is progressing; billing stability "
        f"is the main risk to the sprint goal."
    )


def role_dashboard(db: Session, role: Role, space: Space):
    if role == Role.product_owner:
        return build_dashboard_po(db, space)
    return build_dashboard_developer(db, space)
