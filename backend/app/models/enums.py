"""Domain enums (string-valued so they serialize cleanly and store portably)."""
from __future__ import annotations

import enum


class IssueType(str, enum.Enum):
    story = "story"
    bug = "bug"
    task = "task"
    epic = "epic"  # epic == Feature (a parent work item)


class Status(str, enum.Enum):
    backlog = "backlog"
    todo = "todo"
    inprogress = "inprogress"
    review = "review"
    done = "done"


class Space(str, enum.Enum):
    features = "features"
    support = "support"


class PrState(str, enum.Enum):
    open = "open"
    draft = "draft"
    merged = "merged"


class CiStatus(str, enum.Enum):
    passing = "passing"
    failing = "failing"
    pending = "pending"


class ReviewState(str, enum.Enum):
    approved = "approved"
    pending = "pending"
    changes = "changes"


class Role(str, enum.Enum):
    developer = "developer"
    product_owner = "product_owner"


class EmailCategory(str, enum.Enum):
    customer = "customer"        # customer / support threads
    internal = "internal"        # teammates
    notification = "notification"  # tool notifications (GitHub, CI, etc.)
    newsletter = "newsletter"    # digests, marketing
    alert = "alert"              # on-call / incident / billing alerts
    meeting = "meeting"          # calendar invites & meeting notes


class IgnoreField(str, enum.Enum):
    sender = "sender"    # exact from-address
    domain = "domain"    # from-address domain
    category = "category"  # an EmailCategory value
    keyword = "keyword"  # substring in subject/preview/body
