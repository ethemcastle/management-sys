# 02 · Data Model

Entities, enums, and relationships behind risr/crm, with SQLAlchemy 2.x models and Pydantic v2
schemas. The seed data in `07_SEED_DATA.json` conforms exactly to this.

## Enums

| Enum | Values | Notes / UI |
|------|--------|-----------|
| `IssueType` | `story`, `bug`, `task`, `epic` | `epic` = **Feature** (a parent). Badge letters S/B/T/E; colors in tokens. |
| `Priority` | `0` Low, `1` Medium, `2` High, `3` Urgent | Rendered as a 3-bar glyph; more bars + hotter color as it rises. |
| `Status` | `backlog`, `todo`, `inprogress`, `review`, `done` | Board columns are todo→inprogress→review→done; backlog lives in Backlog view. |
| `Space` | `features`, `support` | Features uses sprints/roadmap; Support is triaged + has AI "solve". |
| `PrState` | `open`, `draft`, `merged` | Colored dot: open=info, draft=muted, merged=purple. |
| `CiStatus` | `passing`, `failing`, `pending` | Dot/icon: green / red / amber (amber spins). |
| `ReviewState` | `approved`, `pending`, `changes` | green check / amber clock / red x. |
| `Role` | `developer`, `product_owner` | (Manager is a future role; same app, PO view is the closest today.) |

## Relationships
- A **Feature** is an `Issue` with `type = epic`. Other issues reference it via `feature_key`
  (nullable FK to `issues.key`). **Features contain tasks** → `feature.children` = all issues whose
  `feature_key` == that feature's key. A child exposes its parent feature.
- An **Issue** optionally belongs to a **Sprint** (`sprint_id`, nullable). Features are not on the board.
- An **Issue** optionally has one **PullRequest** (1:1) and many **Comments**.
- **Assignee**, comment authors, and reviewers are **TeamMembers** (keyed by 2-letter `initials`).
- A **PullRequest** has many **Reviewers** (member + `ReviewState`).

## SQLAlchemy models (abbreviated)

```python
# models/enums.py
import enum
class IssueType(str, enum.Enum):  story="story"; bug="bug"; task="task"; epic="epic"
class Status(str, enum.Enum):     backlog="backlog"; todo="todo"; inprogress="inprogress"; review="review"; done="done"
class Space(str, enum.Enum):      features="features"; support="support"
class PrState(str, enum.Enum):    open="open"; draft="draft"; merged="merged"
class CiStatus(str, enum.Enum):   passing="passing"; failing="failing"; pending="pending"
class ReviewState(str, enum.Enum):approved="approved"; pending="pending"; changes="changes"

# models/member.py
class TeamMember(Base):
    __tablename__ = "members"
    initials: Mapped[str] = mapped_column(String(4), primary_key=True)   # "AL"
    name:     Mapped[str]
    color:    Mapped[str]                                                # "#0E7C86"
    role:     Mapped[str]                                                # developer | product_owner
    is_current_user: Mapped[bool] = mapped_column(default=False)

# models/sprint.py
class Sprint(Base):
    __tablename__ = "sprints"
    id: Mapped[str] = mapped_column(primary_key=True)                    # "s24"
    name: Mapped[str]; range: Mapped[str]; goal: Mapped[str] = mapped_column(default="")
    days_left: Mapped[int | None]; days_total: Mapped[int]
    capacity: Mapped[int | None]; active: Mapped[bool] = mapped_column(default=False)

# models/issue.py
class Issue(Base):
    __tablename__ = "issues"
    key:        Mapped[str] = mapped_column(primary_key=True)            # "CAD-142"
    type:       Mapped[IssueType]
    title:      Mapped[str]
    priority:   Mapped[int] = mapped_column(default=1)                   # 0..3
    status:     Mapped[Status] = mapped_column(default=Status.backlog)
    space:      Mapped[Space]
    points:     Mapped[int] = mapped_column(default=0)
    assignee_initials: Mapped[str | None] = mapped_column(ForeignKey("members.initials"))
    feature_key:       Mapped[str | None] = mapped_column(ForeignKey("issues.key"))   # parent Feature
    sprint_id:         Mapped[str | None] = mapped_column(ForeignKey("sprints.id"))
    branch:     Mapped[str | None]
    blocked:    Mapped[bool] = mapped_column(default=False)
    review_requested: Mapped[bool] = mapped_column(default=False)
    labels:     Mapped[list[str]] = mapped_column(JSON, default=list)    # ["frontend","design"]
    comment_count: Mapped[int] = mapped_column(default=0)

    assignee = relationship("TeamMember")
    children = relationship("Issue", backref=backref("feature", remote_side=[key]))
    pr       = relationship("PullRequest", back_populates="issue", uselist=False)
    comments = relationship("Comment", back_populates="issue", order_by="Comment.created_at")

# models/pull_request.py
class PullRequest(Base):
    __tablename__ = "pull_requests"
    num:      Mapped[int] = mapped_column(primary_key=True)              # 812
    issue_key:Mapped[str] = mapped_column(ForeignKey("issues.key"))
    title:    Mapped[str]; branch: Mapped[str | None]
    state:    Mapped[PrState]; checks: Mapped[CiStatus]
    additions: Mapped[int] = mapped_column(default=0)
    deletions: Mapped[int] = mapped_column(default=0)
    files_changed: Mapped[int] = mapped_column(default=0)
    ai_generated: Mapped[bool] = mapped_column(default=False)           # true for AI-created PRs
    issue = relationship("Issue", back_populates="pr")
    reviewers = relationship("Reviewer")

# models/reviewer.py
class Reviewer(Base):
    __tablename__ = "reviewers"
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    pr_num: Mapped[int] = mapped_column(ForeignKey("pull_requests.num"))
    member_initials: Mapped[str] = mapped_column(ForeignKey("members.initials"))
    state: Mapped[ReviewState] = mapped_column(default=ReviewState.pending)

# models/comment.py
class Comment(Base):
    __tablename__ = "comments"
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    issue_key: Mapped[str] = mapped_column(ForeignKey("issues.key"))
    author_initials: Mapped[str] = mapped_column(ForeignKey("members.initials"))
    kind: Mapped[str] = mapped_column(default="comment")               # comment | commit
    body: Mapped[str]
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    issue = relationship("Issue", back_populates="comments")
```

> `PullRequest.num` as PK matches the design (PRs are referenced as `#812`). If you prefer a surrogate
> id, keep `num` unique. The seed's per-issue `pr` object maps 1:1 to a `PullRequest` row.

## Pydantic response shape (what the frontend consumes)

The frontend expects a **denormalized, display-ready** issue. Resolve members to `{initials,name,color}`
and include derived flags so the UI doesn't recompute business rules. Example:

```jsonc
{
  "key": "CAD-142",
  "type": "story",              // → badge S, color from tokens
  "title": "Redesign onboarding checklist stepper",
  "priority": 3,                // → 3 bars, "Urgent"
  "status": "inprogress",
  "space": "features",
  "points": 5,
  "assignee": { "initials": "AR", "name": "Aria Rahman", "color": "#E8833A" },
  "feature": { "key": "CAD-100", "title": "Onboarding revamp", "color": "#5A50E1" },  // parent, or null
  "sprint": "s24",
  "labels": [ { "name": "frontend", "color": "#3B7DD8" }, { "name": "design", "color": "#D95340" } ],
  "blocked": false,
  "reviewRequested": true,
  "commentCount": 6,
  "pr": {
    "num": 812, "title": "Redesign onboarding checklist stepper",
    "branch": "feat/onboarding-stepper", "state": "open", "checks": "passing",
    "additions": 142, "deletions": 38, "filesChanged": 7, "aiGenerated": false,
    "reviewers": [ { "member": {"initials":"SL","name":"Sena Liu","color":"#B45AF2"}, "state": "changes" } ]
  }
}
```

A **Feature** (type `epic`) additionally returns `children` (array of child issues, or their keys) and
`childProgress` (`{ done, total }`) — see the Issue-detail spec in `05_SCREENS.md`.
