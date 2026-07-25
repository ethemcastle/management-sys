# 06 · Interactions & Behavior

How the app behaves. The prototype fakes data + latency; you'll wire these to the API in
`03_API_CONTRACT.md`. Match the states and transitions.

## Navigation
- Sidebar nav switches the **view** (route). Home resolves to the Developer **or** Product Owner
  dashboard based on the current role.
- Clicking any issue row/card → **issue detail**; a "Back" button returns to the view you came from
  (remember the origin view). Opening a nested issue (feature→task or task→feature) updates the origin.
- Global search and "New" can be stubbed initially (search = filter the current list; New = POST issue).

## Role / Space / Theme (WorkspaceStore, persisted to localStorage)
- **Role** (`developer` | `product_owner`) — changes only the Home dashboard. Segmented control in the
  sidebar footer. Persist; default `developer`.
- **Space** (`features` | `support`) — changes the dataset everywhere and which views apply (Timeline is
  Features-only; Support gets the AI "Solve ticket" action and a triage-style Backlog). Persist.
- **Theme** (`light` | `dark`) — sets `data-theme` on `<html>`; all colors are CSS custom properties.
  Toggle button in the sidebar footer (sun/moon). Persist; default `light`.

## Kanban drag-and-drop (Angular CDK `DragDropModule`)
- Columns are `cdkDropList` connected to each other; cards are `cdkDrag`.
- On drop into a different column, **PATCH `/api/issues/{key}` `{ status }`** and update the card
  optimistically (revert on error). Points/counts and WIP indicators recompute live.
- Visual: dragged card → ~0.35 opacity; hovered column → `--accent-soft` bg + dashed `--accent` outline
  (`outline-offset:-4px`); cursor `grab`/`grabbing`.
- **WIP limits** (To Do 6 / In Progress 4 / In Review 3): show the count vs limit and turn the indicator
  red when over. The prototype does **not** hard-block the drop — treat it as a warning (you may add a
  confirm later). Done has no limit.
- Reordering *within* a column is not tracked in the prototype (status change is what matters). Add
  explicit ordering only if you want it (would need an `order` field + PATCH).

## AI flows (all behind `AiService`; mock first)
Each issue keeps its own AI state so navigating away/back is consistent (store keyed by issue key).

**Summarize thread** (Features issues, and secondary on Support):
1. Click "Summarize thread" → button/card enters **loading** ("Reading N comments and the linked PR…").
2. `POST /api/ai/issues/{key}/summarize` → render **bullets** + a **Suggested resolution** (summary +
   file chips) + a **"Create PR with this fix"** button.
3. Click that → **creating** spinner → `POST /api/ai/issues/{key}/create-pr` → **success**: a green
   confirmation ("Opened PR #834 on cadence-ai/{key}-fix") AND a new **AI PR row appears in the
   Development section** (purple "AI" tag, checks pending). The PR badge also shows on board/list.

**Solve ticket with AI** (Support tickets — the primary action):
1. Click "Solve ticket with AI" → **running** ("Diagnosing the ticket, writing a fix and opening a
   PR…").
2. `POST /api/ai/tickets/{key}/solve` → **solved**: green banner "risr/crm AI opened PR #834 with a
   fix", a "What it changed" summary + file chips, and the AI PR in the Development section. One click,
   end-to-end.

**risr/crm AI slide-over** (global assistant):
- Opens from sidebar "risr/crm AI", top-bar "Ask AI", dashboard AI buttons.
- Suggestion chip or Enter → **busy** ("Analyzing your workspace…") → `POST /api/ai/assistant` →
  **done** (titled bullet list + Copy / Create report). Idle state shows an empty prompt.
- Closes on scrim click or the ✕.

**Dashboard AI** (server-provided, no interaction needed): Developer "Your standup" bullets and PO
"Weekly report" + "Risks" come from `GET /api/dashboard` — render as static AI-authored content with a
regenerate affordance.

> Mock latency ≈ 1.5–2s in the prototype. Keep the loading states even with a fast real backend; if the
> real call is <300ms, hold the spinner briefly so the transition reads.

## Features contain tasks (parent/child)
- A **Feature** = issue `type=epic`. Its detail shows a **Tasks** list of children with a done/total
  progress bar; checking/among children is reflected in the bar.
- A child issue shows a clickable **Feature** chip in its right-rail Details → opens the parent.
- Features are **excluded** from the Board and Backlog lists (they're containers), but appear in List
  (a "Features" group), Timeline (one row each), and the PO "Epic progress" widget — all clickable.

## Loading / empty / error states
- **Loading:** view-level skeletons or a subtle fade-in; AI actions use inline spinners (above).
- **Empty:** dashed-border placeholder with a short message (e.g. Timeline in Support space; a column
  with no issues shows "No issues").
- **Unassigned:** dashed circle instead of an avatar.
- **Blocked:** red "BLOCKED" pill on cards/rows.
- **Error:** revert optimistic UI and surface a small toast/inline message (not specced visually —
  use the danger tokens).

## Responsive
The prototype is a desktop app designed ~1280–1440px wide; the board scrolls horizontally. A full
responsive/mobile pass was **not** designed — treat ≥1024px as the target and degrade gracefully
(collapse the sidebar to icons, stack dashboard columns) only if you need it. Confirm with the
designer before investing in a mobile layout.

## Persistence summary
- localStorage: `theme`, `role`, `space` (and the tweak knobs: accent, radius, density if you expose them).
- Server: all issue/PR/comment mutations. AI-created PRs persist so the board/list/detail stay consistent.
