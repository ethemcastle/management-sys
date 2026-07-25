# risr/crm

A Jira-class task manager for software teams, with **GitHub** and **AI** woven in —
built from the design handoff in [`design_handoff_cadence/`](design_handoff_cadence).

- **Two spaces:** Features (product development — sprints, epics, roadmap) and Product Support
  (customer tickets — triaged, with a one-click AI "Solve ticket → open a PR" flow).
- **Seven core views:** Home (role-specific dashboard), Board (Kanban drag-and-drop with WIP
  limits), Backlog (sprint planning + capacity), List (grouped table), Timeline (roadmap), Reports
  (burndown / velocity / cycle-time / distribution), and Issue detail.
- **Inbox:** an email inbox with an **AI recap** (grouped by type) and **ignore rules** — hide
  noisy email types by sender / domain / category / keyword; the recap skips ignored mail.
- **Calendar:** connects to **Google Calendar** (mocked) to import the week's meetings (with Meet
  links) and generate an **AI meeting recap** per event that is persisted to the DB.
- **Features contain tasks:** a Feature is an epic parent; its detail lists child tasks with a
  progress bar; children link back up.
- **GitHub as data:** issues show linked branches, PRs, CI checks, and reviewers.
- **risr/crm AI:** summarize an issue thread, create an AI-authored PR, solve a support ticket
  end-to-end, a developer standup, PO risk flags + weekly report, and a context-aware assistant panel.

Everything external is mocked behind a small interface so the whole app is demoable offline:
`AiService` (`MockAiService`), `MailService` (`MockMailService` — the inbox + recap), and
`CalendarService` (`MockCalendarService` — the Google Calendar connection + meeting recaps).
Swapping in a real LLM / Gmail / Google Calendar is a one-file change per service.

## Stack

| | |
|---|---|
| **Frontend** | Angular 20 (standalone components, signals, new control flow), Angular CDK (board drag-and-drop, overlays), SCSS with CSS custom-property theming, typed `HttpClient` services |
| **Backend** | Python + FastAPI, SQLAlchemy 2.x (typed), Pydantic v2 (camelCase JSON), Alembic, SQLite for dev / Postgres-ready, Uvicorn |

## Prerequisites

- **Node.js** ≥ 20.19 (or 22.12+, or 24.0+) and npm
- **Python** ≥ 3.11

## Quick start (two terminals)

### 1. Backend → http://localhost:8000  (interactive docs at `/docs`)

```bash
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt          # or: pip install -e .
uvicorn app.main:app --reload --port 8000
```

On first run the app creates the SQLite DB and seeds it from `app/seed_data.json`
(the exact demo data from the design prototype). Delete `backend/app/cadence.db` to reseed.

### 2. Frontend → http://localhost:4200

```bash
cd frontend
npm install
npm start                                 # ng serve
```

The dev server proxies `/api` to the backend (`frontend/proxy.conf.js` → `http://127.0.0.1:8000`),
so requests are same-origin — no CORS, and no `localhost` IPv4/IPv6 ambiguity. Open
http://localhost:4200 and click around: switch role (Developer/Product) and space
(Features/Product Support) in the sidebar, toggle light/dark, drag cards on the Board, open an
issue, run the AI flows, recap the **Inbox** (and add ignore rules), and connect the **Calendar**
to generate meeting recaps.

## Docker (local dev)

```bash
docker compose up --build
# API → http://localhost:8000   ·   App → http://localhost:4200
```

## Database migrations (Alembic)

Tables are auto-created on startup for dev convenience. For a migration-driven setup (e.g. Postgres):

```bash
cd backend
alembic upgrade head                      # apply migrations
alembic revision --autogenerate -m "..."  # create a new migration after model changes
```

Point at Postgres by setting `CADENCE_DATABASE_URL`, e.g.
`postgresql+psycopg://user:pass@localhost:5432/cadence` (install the `postgres` extra).

## Plugging in real services (LLM / Gmail / Google Calendar)

Everything external is behind an interface with a mock implementation. To go live, implement the
interface and return your instance from the `get_*` factory — no endpoint, schema, or frontend
change is required (response shapes are fixed by the API contract):

| Concern | File | Interface → mock → factory |
|---|---|---|
| AI (issue summaries, PRs, assistant) | `app/services/ai_service.py` | `AiService` → `MockAiService` → `get_ai_service()` |
| Email (inbox + recap) | `app/services/mail_service.py` | `MailService` → `MockMailService` → `get_mail_service()` |
| Calendar (Google connect + meeting recaps) | `app/services/calendar_service.py` | `CalendarService` → `MockCalendarService` → `get_calendar_service()` |

```python
class AiService(ABC): ...           # the interface
class MockAiService(AiService): ... # deterministic, ships by default
# add:  class LlmAiService(AiService): ...
def get_ai_service() -> AiService:  # swap the returned instance here
```

## Project structure

```
.
├── backend/                  # FastAPI + SQLAlchemy + Pydantic
│   ├── app/
│   │   ├── models/           # ORM (issue, member, sprint, pull_request, reviewer, comment, email, calendar)
│   │   ├── schemas/          # Pydantic v2 (camelCase) request/response
│   │   ├── routers/          # meta, issues, board, backlog, sprints, reports, timeline,
│   │   │                     #   dashboard, ai, emails, calendar
│   │   ├── services/         # ai_service, mail_service, calendar_service (all mock),
│   │   │                     #   metrics (derived views), serializers, catalog
│   │   ├── seed.py           # loads seed_data.json + synthesizes activity, inbox, calendar account
│   │   └── main.py           # app, CORS, lifespan (create + seed)
│   └── alembic/              # migrations
├── frontend/                 # Angular 20
│   ├── proxy.conf.js         # dev-server /api proxy → backend
│   └── src/app/
│       ├── core/             # models, api/ (typed services), stores/ (workspace, ai, ui), theme
│       ├── layout/           # sidebar, top-bar, ai-panel (slide-over)
│       ├── shared/           # avatar, priority-bars, type-badge, status-pill, pr-badge, ci-dot, …
│       └── features/         # home, board, backlog, list, timeline, reports, issue-detail,
│                             #   inbox, calendar
├── design_handoff_cadence/   # the original design spec (00–07 + HTML prototype)
└── docker-compose.yml
```

## Functional scope

Everything is backed by the API and persists to the database. All example data lives in **one seed
script** (`backend/app/seed.py` + `app/seed_data.json`) — change the mocks there and re-seed
(delete `backend/app/cadence.db`) to change what the whole app shows.

**Fully functional (real, persisted CRUD):**
- Create tickets — top-bar **New** opens a full **ticket modal** (type, title, space, priority,
  status, points, assignee, sprint, feature, labels); plus per-column **Add issue** on the Board,
  per-group **Add issue** in the Backlog, and **Add task** on a Feature (creates a child).
- Edit issues from the detail page — status, assignee, priority, points, sprint, and blocked all
  patch the backend inline; **drag-and-drop** on the Board patches status.
- **Delete** an issue (detail overflow menu); **Start sprint** in the Backlog.
- **GitHub connection** — connect a repository (`owner/repo`) and risr/crm **identifies branches &
  PRs for each ticket by its code** (issue key): a branch `feat/CAD-142-…` or a PR titled
  `CAD-142: …` auto-links to `CAD-142`. Shown in the issue's Development section. (Repo data is still
  a mock pool behind `MockGitHubService`; the real GitHub API is the one-file swap — the connect +
  key-matching mechanism is real.)
- Comments, inbox recap + ignore rules, and all the server-computed views (board, backlog, reports,
  timeline, dashboards).

**Still mocked (deferred — swap the service impl later, no API/UI change):**
- **AI** — summaries, PR creation, ticket solving, assistant, recaps (`MockAiService`/`MockMailService`).
- **Calendar** — the Google connection and meeting recaps (`MockCalendarService`).
- **GitHub repo contents** — the branch/PR pool is mock data (`MockGitHubService`); real GitHub API
  auth + fetching is the remaining swap.

## Notes

- **Auth** is out of scope for the prototype; the current user is Alex Rivera (`AL`). FastAPI keeps a
  `get_current_user` dependency as the seam for a real auth layer.
- **Theme / role / space** persist to `localStorage`; the theme is applied to `<html>` before first
  paint (no flash). Tweak knobs (accent, radius) are wired through the same store.
- **AI-created PRs persist**, so the board/list/detail stay consistent after an AI flow. The first AI
  PR number is `834` (matching the prototype); subsequent ones increment.
