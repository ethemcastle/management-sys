"""Composite response schemas for the server-computed views."""
from __future__ import annotations

from datetime import datetime
from typing import Literal

from app.models.enums import Role, Status
from app.schemas.common import CamelModel
from app.schemas.entities import (
    IssueOut,
    MemberOut,
    MemberRef,
    SpaceOut,
    SprintOut,
)


# ---- bootstrap -------------------------------------------------------------
class BootstrapOut(CamelModel):
    current_user: MemberOut
    members: list[MemberOut]
    spaces: list[SpaceOut]
    sprints: list[SprintOut]
    labels: dict[str, str]


# ---- board -----------------------------------------------------------------
class BoardColumn(CamelModel):
    key: Status
    title: str
    wip_limit: int
    count: int
    issues: list[IssueOut]


class BoardOut(CamelModel):
    columns: list[BoardColumn]


# ---- backlog ---------------------------------------------------------------
class BacklogGroup(CamelModel):
    id: str
    name: str
    meta: str = ""
    active: bool = False
    capacity: int | None = None
    points: int = 0
    count: int = 0
    issues: list[IssueOut]


class BacklogOut(CamelModel):
    groups: list[BacklogGroup]


# ---- sprint health ---------------------------------------------------------
class SprintHealthOut(CamelModel):
    committed: int
    done: int
    in_progress: int
    review: int
    todo: int
    remaining: int
    scope_added: int
    on_track: bool


# ---- reports ---------------------------------------------------------------
class StatCard(CamelModel):
    label: str
    value: str
    unit: str = ""
    delta: str = ""
    good: bool = True


class Burndown(CamelModel):
    max: int
    ideal: list[float]
    actual: list[float]
    days: list[str]


class VelocityBar(CamelModel):
    sprint: str
    committed: int
    completed: int


class DistributionSlice(CamelModel):
    status: Status
    label: str
    count: int


class ReportsOut(CamelModel):
    stats: list[StatCard]
    burndown: Burndown
    velocity: list[VelocityBar]
    distribution: list[DistributionSlice]


# ---- timeline --------------------------------------------------------------
class TimelineMonth(CamelModel):
    label: str
    start_week: int
    span_weeks: int


class TimelineRow(CamelModel):
    feature_key: str
    name: str
    color: str
    start_week: int
    span_weeks: int
    progress: float


class TimelineOut(CamelModel):
    months: list[TimelineMonth]
    today_week: int
    rows: list[TimelineRow]


# ---- dashboard -------------------------------------------------------------
class RiskItem(CamelModel):
    issue: IssueOut
    reason: str


class WorkloadRow(CamelModel):
    member: MemberRef
    points: int
    overloaded: bool = False


class EpicProgressRow(CamelModel):
    key: str
    title: str
    color: str
    done: int
    total: int
    progress: float


ActionType = Literal[
    "ci_failing", "changes_requested", "review_request", "blocked", "monday_unsynced"
]


class ActionItem(CamelModel):
    """One thing in the developer's "Needs you" queue. `issue` carries the code +
    sync signals (pr/checks/blocked/syncState/mondayStatus) already; `severity`
    is the sort key (higher = more urgent)."""

    kind: ActionType
    issue: IssueOut
    reason: str
    severity: int


class MondaySummary(CamelModel):
    pending_count: int = 0
    last_synced_at: datetime | None = None


class DashboardDeveloper(CamelModel):
    my_focus: list[IssueOut]
    review_queue: list[IssueOut]
    my_prs: list[IssueOut]
    standup: list[str]
    sprint_health: SprintHealthOut
    # "Needs you" cockpit: a ranked, deduped action queue + supporting signals.
    action_items: list[ActionItem] = []
    blocked: list[IssueOut] = []
    failing_ci: list[IssueOut] = []
    monday: MondaySummary = MondaySummary()


class DashboardPo(CamelModel):
    sprint_health: SprintHealthOut
    risks: list[RiskItem]
    workload: list[WorkloadRow]
    epic_progress: list[EpicProgressRow]
    weekly_report: str


class DashboardOut(CamelModel):
    """Role-tagged wrapper; exactly one of developer/po is populated."""

    role: Role
    developer: DashboardDeveloper | None = None
    po: DashboardPo | None = None
