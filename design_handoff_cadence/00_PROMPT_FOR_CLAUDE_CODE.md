# Prompt for Claude Code

> Paste everything in the box below into Claude Code, from the repo root, with this
> `design_handoff_cadence/` folder present. It refers to the other files by name, so keep the
> folder intact. Delete the two lines at the very top if you like.

---

```
You are building **Cadence**, a Jira-class task manager for software teams, with GitHub and AI
integrations. I've given you a complete design handoff in `design_handoff_cadence/`. Read it
before writing code:

- design_handoff_cadence/README.md            — overview + how the pieces fit
- design_handoff_cadence/01_ARCHITECTURE.md    — the stack, folder layout, and build order
- design_handoff_cadence/02_DATA_MODEL.md      — entities, enums, relationships
- design_handoff_cadence/03_API_CONTRACT.md    — every REST endpoint I want
- design_handoff_cadence/04_DESIGN_TOKENS.md   — exact colors/type/spacing (HIGH fidelity — match them)
- design_handoff_cadence/05_SCREENS.md         — every screen, component-by-component
- design_handoff_cadence/06_INTERACTIONS.md    — drag-and-drop, AI flows, theming, states
- design_handoff_cadence/07_SEED_DATA.json     — demo data; seed the DB with exactly this
- design_handoff_cadence/design/Cadence.dc.html — the interactive HTML PROTOTYPE (design reference)

IMPORTANT: The HTML file is a DESIGN REFERENCE, not code to copy. Open it in a browser to see the
intended look and behavior, then rebuild it properly in the stack below. Do not port its
prototype runtime (support.js) — that's throwaway.

## Stack (use exactly this unless I say otherwise)
- Frontend: Angular (latest), standalone components, signals for state, Angular Router,
  Angular CDK (drag-and-drop for the board), SCSS with CSS custom properties for theming,
  HttpClient with typed services. No component library — build the UI from the design tokens.
- Backend: Python with FastAPI, SQLAlchemy 2.x (ORM), Pydantic v2 (schemas), Alembic (migrations),
  SQLite for dev / Postgres-ready. Uvicorn to serve.
- Tooling: a single repo with `/frontend` and `/backend`. Provide a README with run instructions
  and a docker-compose for local dev.

## What to build, in order
1. Backend skeleton: FastAPI app, DB session, models from 02_DATA_MODEL.md, Alembic migration,
   and a seed script that loads 07_SEED_DATA.json verbatim.
2. Implement the REST API in 03_API_CONTRACT.md, including the GitHub-facing fields and the two
   AI endpoints (summarize issue thread; solve support ticket → create PR). For the AI endpoints,
   stub the "AI" behind a service interface (AiService) with a deterministic mock implementation
   that returns the shaped responses in the contract, so the UI works end-to-end without a real
   model. Leave a clear extension point to plug in a real LLM later.
3. Frontend app shell: sidebar + top bar + theming (light/dark via CSS custom properties, exactly
   the tokens in 04_DESIGN_TOKENS.md), role switch (Developer/Product Owner), space switch
   (Features/Product Support). Persist theme + role + space in a signal store and localStorage.
4. The seven views in 05_SCREENS.md, wired to the API: Home (role-specific dashboard), Board,
   Backlog, List, Timeline, Reports, and the Issue detail page.
5. Interactions in 06_INTERACTIONS.md: Kanban drag-and-drop that PATCHes issue status and respects
   WIP limits; the AI slide-over panel; the "Summarize thread" and "Solve ticket with AI → PR"
   flows with their loading→result states; feature→tasks parent/child navigation.

## Fidelity bar
Match the design tokens and layouts precisely (spacing, radii, font sizes, the light AND dark
palettes). Use the exact copy from 05_SCREENS.md. Reproduce the priority "bar" glyph, type/status
color coding, avatar chips (2-letter monogram on a per-user color), and PR/CI status dots as
specified. Font is Hanken Grotesk (UI) + JetBrains Mono (keys, points, code-ish values).

## Data model must-haves (details in 02/03)
- An Issue has: key, type (story|bug|task|epic), priority (0–3), status
  (backlog|todo|inprogress|review|done), assignee, story points, optional parent Feature,
  optional sprint, space (features|support), labels, comments, and an optional linked PR.
- A **Feature is an issue of type `epic`** and is the PARENT of many task/story/bug issues
  (features contain tasks). Expose children on the feature and the parent on each child.
- A PR has: number, state (open|draft|merged), CI checks (passing|failing|pending), title, branch,
  additions/deletions/files, and reviewers (approved|pending|changes).

Ask me before deviating from the contract or the visual spec. When each layer is working, show me
how to run it and give a short walkthrough. Start by reading the handoff files and outlining your
plan, then build backend-first.
```

---

## Tips for driving the build

- **Build backend-first** so the frontend has real endpoints to hit. The prompt already asks for this.
- If Claude Code proposes a different framework (React, Vue) — that's the prototype's influence.
  Steer it back to **Angular + FastAPI**; the design is framework-agnostic.
- The AI features are the differentiator. Keep them behind an `AiService` interface with a mock
  implementation first (the contract in `03_API_CONTRACT.md` defines the exact response shapes), so
  the whole app is demoable offline. Swapping in a real LLM later is then a one-file change.
- After the first pass, open the prototype and the app side-by-side and fix fidelity gaps against
  `04_DESIGN_TOKENS.md` and `05_SCREENS.md`.
