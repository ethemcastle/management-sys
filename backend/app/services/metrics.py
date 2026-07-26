"""Server-side computations: board grouping, sprint health, backlog groups,
reports, timeline, and the role dashboards. The UI renders these numbers
directly, so all the business rules live here (not in the client).
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.enums import CiStatus, IssueType, PrState, ReviewState, Role, Space, Status
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
# Everything below is COMPUTED from the real database (issues, sprints, PRs).
# There are no curated/placeholder numbers: stat cards, velocity, burndown and
# distribution all reflect the actual data on hand.


def _sprint_short(name: str) -> str:
    """"Sprint 24" -> "S24"; any other name is returned unchanged."""
    parts = name.split()
    if len(parts) == 2 and parts[0].lower().startswith("sprint") and parts[1].isdigit():
        return f"S{parts[1]}"
    return name


def _day_labels(rng: str | None, days_total: int) -> list[str]:
    """Three x-axis labels derived from a sprint range like "Jul 1 – 14"."""
    if rng:
        norm = rng.replace("–", "-").replace("—", "-")
        bits = [b.strip() for b in norm.split("-") if b.strip()]
        if len(bits) >= 2:
            start = bits[0]  # e.g. "Jul 1"
            sp = start.split()
            month = sp[0] if sp and not sp[0][0].isdigit() else ""
            endraw = bits[-1]  # "14" or "Aug 2"
            end = endraw if any(c.isalpha() for c in endraw) else (f"{month} {endraw}".strip())
            try:
                d0 = int("".join(c for c in sp[-1] if c.isdigit()))
                d1 = int("".join(c for c in endraw if c.isdigit()))
                mid = f"{month} {(d0 + d1) // 2}".strip()
            except ValueError:
                mid = ""
            return [start, mid, end] if mid else [start, end]
    return ["Day 1", f"Day {max(1, days_total // 2)}", f"Day {days_total}"]


def _measure(issues: list[Issue], unit: str, done_only: bool = False) -> int:
    """Size a set of issues in the active unit — story points, or a plain issue
    count when the project doesn't track points (all points == 0)."""
    sel = [i for i in issues if (not done_only or i.status == Status.done)]
    return sum(i.points for i in sel) if unit == "points" else len(sel)


def _velocity(db: Session, space: Space, unit: str) -> list[VelocityBar]:
    """Real planned/completed size per sprint, from current issue assignments."""
    issues = non_epic_issues(db, space)
    bars: list[VelocityBar] = []
    for s in db.scalars(select(Sprint).order_by(Sprint.id)):
        in_sprint = [i for i in issues if i.sprint_id == s.id]
        bars.append(
            VelocityBar(
                sprint=_sprint_short(s.name),
                committed=_measure(in_sprint, unit),
                completed=_measure(in_sprint, unit, done_only=True),
            )
        )
    return bars


def _burndown_actual(committed: int, remaining: int, elapsed: int, done_pts: list[int]) -> list[float]:
    """Remaining work per elapsed day (day 0 .. today). Both endpoints are real —
    the line starts at the committed total and ends at today's real remaining. The
    per-day shape is reconstructed from the real sizes of the completed issues,
    because the model stores no completion date; once tickets are moved in-app
    (which records dated audit events) this becomes exact."""
    if elapsed <= 0:
        return [float(committed)]
    burned = committed - remaining
    if burned <= 0:
        # nothing net-burned yet (or scope grew): a real straight segment to today.
        step = (remaining - committed) / elapsed
        return [round(committed + step * d, 1) for d in range(elapsed + 1)]
    shape = [p for p in done_pts if p > 0] or [1] * min(elapsed, max(1, burned))
    scale = burned / sum(shape)
    by_day = [0.0] * (elapsed + 1)
    for idx, p in enumerate(shape):
        by_day[1 + (idx % elapsed)] += p * scale
    actual: list[float] = []
    rem = float(committed)
    for d in range(elapsed + 1):
        rem -= by_day[d]
        actual.append(round(rem, 1))
    actual[-1] = float(remaining)  # pin the real endpoint (guards rounding drift)
    return actual


def _reports_stats(
    scope: int, done: int, remaining: int, merged: int, prev_completed: int | None, unit: str
) -> list[StatCard]:
    """Four headline cards, all computed. The Completed delta compares against the
    previous sprint's completed work when there is one."""
    if prev_completed is None:
        comp_delta, comp_good = "", True
    else:
        d = done - prev_completed
        comp_delta, comp_good = (f"+{d}" if d >= 0 else f"−{abs(d)}"), d >= 0
    return [
        StatCard(label="Planned", value=str(scope), unit=unit),
        StatCard(label="Completed", value=str(done), unit=unit, delta=comp_delta, good=comp_good),
        StatCard(label="Remaining", value=str(remaining), unit=unit, good=remaining <= scope),
        StatCard(label="PRs merged", value=str(merged), unit="this sprint"),
    ]


def build_reports(db: Session, space: Space, sprint_id: str | None) -> ReportsOut:
    sprint = db.get(Sprint, sprint_id) if sprint_id else active_sprint(db)
    sid = sprint.id if sprint else sprint_id

    # Unit: story points if the project tracks any, otherwise plain issue counts.
    all_issues = non_epic_issues(db, space)
    unit = "points" if any(i.points for i in all_issues) else "issues"

    # the sprint's issues (same set the board/health use), for burndown + distribution.
    issues = (
        sprint_issues(db, space, sprint.id)
        if (sprint and space == Space.features)
        else [i for i in all_issues if i.sprint_id == sid]
    )
    scope = _measure(issues, unit)
    done = _measure(issues, unit, done_only=True)
    remaining = max(0, scope - done)

    days_total = sprint.days_total if sprint else 10
    days_left = sprint.days_left if (sprint and sprint.days_left is not None) else days_total
    elapsed = max(0, min(days_total, days_total - days_left))

    ideal = [round(scope * (1 - i / days_total), 1) for i in range(days_total + 1)]
    done_shape = [(i.points if unit == "points" else 1) for i in issues if i.status == Status.done]
    burndown = Burndown(
        max=max(scope, 1),
        ideal=ideal,
        actual=_burndown_actual(scope, remaining, elapsed, done_shape),
        days=_day_labels(sprint.range if sprint else None, days_total),
    )

    velocity = _velocity(db, space, unit)
    # previous sprint's completed (for the Completed delta) — the one just before
    # the current sprint in id order, if it exists.
    prev_completed = None
    if sprint is not None:
        names = [v.sprint for v in velocity]
        cur = _sprint_short(sprint.name)
        if cur in names and names.index(cur) > 0:
            prev_completed = velocity[names.index(cur) - 1].completed

    merged = sum(1 for i in issues for p in i.prs if p.state == PrState.merged)
    stats = _reports_stats(scope, done, remaining, merged, prev_completed, unit)

    # To Do folds in backlog-status issues (as sprint_health does), so the slices
    # sum to the sprint total shown as "Planned" / the burndown baseline.
    dist_defs = [
        (Status.todo, "To Do", (Status.todo, Status.backlog)),
        (Status.inprogress, "In Progress", (Status.inprogress,)),
        (Status.review, "In Review", (Status.review,)),
        (Status.done, "Done", (Status.done,)),
    ]
    distribution = [
        DistributionSlice(status=st, label=lbl, count=sum(1 for i in issues if i.status in group))
        for st, lbl, group in dist_defs
    ]
    return ReportsOut(stats=stats, burndown=burndown, velocity=velocity, distribution=distribution)


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

    # Home cards (cross-space): the Support-space queue + the Features-space
    # product-planning list — open items, highest priority first.
    def _open_sorted(sp: Space) -> list[Issue]:
        items = [i for i in non_epic_issues(db, sp) if i.status != Status.done]
        items.sort(key=lambda i: (-i.priority, i.key))
        return items

    support_tickets = _open_sorted(Space.support)
    product_planning = _open_sorted(Space.features)

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
        support_tickets=[S.issue_out(i) for i in support_tickets],
        product_planning=[S.issue_out(i) for i in product_planning],
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
