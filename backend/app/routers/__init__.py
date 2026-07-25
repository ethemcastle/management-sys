"""API routers."""
from __future__ import annotations

from app.routers import (
    admin,
    ai,
    backlog,
    board,
    calendar,
    catalog,
    dashboard,
    emails,
    github,
    issues,
    meta,
    monday,
    recaps,
    reports,
    sprints,
    timeline,
    ybug,
    zoom,
)

# Order here is the order they mount in main.py.
all_routers = [
    meta.router,
    issues.router,
    board.router,
    backlog.router,
    sprints.router,
    reports.router,
    timeline.router,
    dashboard.router,
    ai.router,
    emails.router,
    calendar.router,
    recaps.router,
    github.router,
    catalog.router,
    monday.router,
    zoom.router,
    ybug.router,
    admin.router,
]

__all__ = ["all_routers"]
