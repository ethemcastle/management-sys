# 01 · Architecture

Recommended stack and structure for building risr/crm in **Angular + Python**. Adjust to house style,
but keep the contracts in `02_DATA_MODEL.md` and `03_API_CONTRACT.md` stable.

## Stack

### Frontend — Angular
- **Angular** (latest), **standalone components** (no NgModules).
- **Signals** for local + shared state (`signal`, `computed`, `effect`). A small set of injectable
  signal stores: `WorkspaceStore` (role, space, theme), `IssuesStore` (issues cache + mutations),
  `AiStore` (panel open/close + per-issue AI state).
- **Angular Router** for the seven views + issue detail. Space is a query param or store value; the
  view is the route.
- **Angular CDK** — `DragDropModule` for the Kanban board; `OverlayModule` for the AI slide-over and menus.
- **SCSS** with **CSS custom properties** for theming (light/dark) — see `04_DESIGN_TOKENS.md`.
  Global tokens on `:root` and `[data-theme="dark"]`; components consume `var(--…)`. Do NOT hardcode hex.
- **HttpClient** with typed services (one per resource) returning typed models.
- No component/UI kit — build the components from tokens. Icons: inline SVG (stroke-based, 1.7–1.9px)
  or a lightweight set like Lucide. Fonts: **Hanken Grotesk** (UI) and **JetBrains Mono** (keys, points, code).

### Backend — Python
- **FastAPI** (ASGI, auto OpenAPI docs, Pydantic-native).
- **SQLAlchemy 2.x** ORM + **Pydantic v2** schemas (request/response models).
- **Alembic** migrations.
- **SQLite** for dev, Postgres-ready for prod (no SQLite-only column types).
- **Uvicorn** dev server.
- **AI behind an interface:** `AiService` (abstract) + `MockAiService` (deterministic, ships by
  default) + room for `LlmAiService` later. The API shape never changes when you swap the impl.
- **GitHub as data:** model PRs/branches/checks/reviewers as first-class fields on issues (see data
  model). A real GitHub sync can populate them later; for now they come from the seed data.

## Monorepo layout

```
cadence/
├── docker-compose.yml            # frontend + backend for local dev
├── README.md                     # run instructions
├── backend/
│   ├── app/
│   │   ├── main.py               # FastAPI app, CORS, router mounting
│   │   ├── db.py                 # engine, session, Base
│   │   ├── models/               # SQLAlchemy models (see 02)
│   │   │   ├── issue.py  member.py  feature.py  sprint.py  pull_request.py  comment.py
│   │   ├── schemas/              # Pydantic v2 request/response (see 02, 03)
│   │   ├── routers/              # issues.py  board.py  backlog.py  reports.py  ai.py  meta.py
│   │   ├── services/
│   │   │   ├── ai_service.py     # AiService (abstract) + MockAiService
│   │   │   └── metrics.py        # sprint health, burndown, velocity, workload calcs
│   │   └── seed.py               # loads ../design_handoff_cadence/07_SEED_DATA.json
│   ├── alembic/                  # migrations
│   └── pyproject.toml
└── frontend/
    ├── src/app/
    │   ├── core/
    │   │   ├── models/           # TS interfaces mirroring the API (Issue, PullRequest, …)
    │   │   ├── api/              # typed HttpClient services (issues.api.ts, ai.api.ts, …)
    │   │   └── stores/           # workspace.store.ts, issues.store.ts, ai.store.ts (signals)
    │   ├── layout/               # shell: sidebar/, top-bar/, ai-panel/
    │   ├── shared/               # issue-card, avatar, priority-bars, type-badge, status-pill,
    │   │                         # pr-badge, ci-check, label-chip, progress-bar
    │   ├── features/
    │   │   ├── dashboard/        # dashboard-developer, dashboard-po
    │   │   ├── board/            # cdk drag-drop
    │   │   ├── backlog/          list/  timeline/  reports/  issue-detail/
    │   ├── styles/               # _tokens.scss (from 04), _base.scss, global.scss
    │   └── app.routes.ts
    └── angular.json
```

## Build order
1. **Backend models + seed + migrations.** Load `07_SEED_DATA.json` exactly.
2. **REST API** per `03_API_CONTRACT.md`, including derived metrics endpoints and the two AI endpoints (mock impl).
3. **Frontend shell + theming + stores** (sidebar, top bar, role/space/theme switches, persistence).
4. **Views** wired to the API, using shared presentational components.
5. **Interactions** (`06_INTERACTIONS.md`): CDK board drag-drop → PATCH status; AI panel; summarize/solve flows; feature↔task nav.

## Cross-cutting
- **Theming:** set `data-theme="light|dark"` on `<html>`; all colors via CSS custom properties.
  Persist choice in localStorage; default light.
- **Role & space** live in `WorkspaceStore`; the Home view and available data change with them, but
  the URL/route stays stable. Persist both.
- **Auth:** out of scope for the prototype. Assume a current user = Alex Rivera (`AL`). Add a real
  auth layer later; keep a `current_user` dependency in FastAPI as the seam.
- **Money/dates/ids:** issue keys are human strings (`CAD-142`, `SUP-402`), not DB ids — keep both.
