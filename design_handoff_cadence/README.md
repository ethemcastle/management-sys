# Cadence — Developer Handoff Package

**Target stack: Angular (frontend) + Python (backend).**

This bundle is everything a developer (or Claude Code) needs to build **Cadence**, a Jira-class
task manager for software teams — with GitHub and AI woven in. It was designed for three roles
(Developer, Product Owner, Manager) and two "spaces" (product Features and Product Support).

---

## ⚠️ Read this first — what the design files are

The files under `design/` are a **design reference built in HTML/CSS/JS** (a single-file interactive
prototype). They exist to show the intended **look, layout, copy, and behavior**. They are **not**
production code to copy, and they are **not** Angular.

Your job is to **recreate this design in a real Angular + Python codebase**, using idiomatic
patterns for each (Angular standalone components + signals + services; Python REST API + ORM).
The prototype fakes its backend with in-memory data and `setTimeout` — you will replace that with
real API calls and a real database.

**Fidelity: HIGH.** Colors, typography, spacing, radii, and interactions in the prototype are final.
Match them pixel-for-pixel. All exact values are in `04_DESIGN_TOKENS.md`.

---

## How to use this bundle

1. **Open the prototype.** Open `design/Cadence.dc.html` in a browser. Click around: switch
   role (Developer/Product Owner) and space (Features/Product Support) in the sidebar, toggle
   light/dark, drag cards on the Board, open an issue, run the AI flows. This is your source of truth.
2. **Give Claude Code the prompt.** `00_PROMPT_FOR_CLAUDE_CODE.md` is a ready-to-paste prompt.
   It references the other files in this folder — keep them together.
3. **Follow the specs** as you build. Each numbered file is one concern.

---

## Files in this bundle

| File | What it covers |
|------|----------------|
| `README.md` | This index. |
| `00_PROMPT_FOR_CLAUDE_CODE.md` | **The prompt.** Paste into Claude Code to kick off the build. |
| `01_ARCHITECTURE.md` | Recommended Angular + Python stack, folder structure, key libraries, build order. |
| `02_DATA_MODEL.md` | Entities, enums, relationships. SQLAlchemy models + Pydantic schemas. |
| `03_API_CONTRACT.md` | REST endpoints with request/response shapes, incl. the AI + GitHub endpoints. |
| `04_DESIGN_TOKENS.md` | Exact colors (light + dark), type scale, spacing, radius, shadows — as SCSS. |
| `05_SCREENS.md` | Every view: purpose, layout, components, exact specs, copy. |
| `06_INTERACTIONS.md` | Drag-and-drop, AI flows, theme/role/space switching, loading states. |
| `07_SEED_DATA.json` | The exact demo data from the prototype — use for DB fixtures / mocks. |
| `design/Cadence.dc.html` | The interactive HTML prototype (design reference). |
| `design/support.js` | Runtime the prototype needs to render. Do not port — it's prototype-only. |

---

## The product in one screen

- **App shell:** left sidebar (workspace + space switcher, primary nav, role switch, user + theme
  toggle) · top bar (breadcrumb, global search, "Ask AI", "New").
- **Two spaces:** **Features** (product development — uses sprints, features/epics, a roadmap) and
  **Product Support** (customer tickets — triaged, not scheduled; has an AI "Solve ticket" flow).
- **Seven views:** Home (role-specific dashboard) · Board (Kanban, drag-and-drop, WIP limits) ·
  Backlog (sprint planning w/ capacity) · List (grouped table) · Timeline (roadmap) ·
  Reports (burndown, velocity, cycle-time, distribution) · Issue detail.
- **Features contain tasks:** a Feature is a parent work item; its detail lists child tasks with a
  progress bar; a child links back up to its Feature.
- **GitHub:** issues show linked branches, PRs, CI check status, and reviewers; "Create branch".
- **AI (Cadence AI):** summarize an issue thread; **solve a support ticket → open a PR with the
  fix**; drafted developer standup; PO risk flags + weekly report; a context-aware assistant panel.

See `05_SCREENS.md` for the full breakdown.
