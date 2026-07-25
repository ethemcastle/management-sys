# 05 · Screens

Every view, component-by-component. Open `design/risr/crm.dc.html` alongside this. Fidelity is HIGH —
match layout, spacing, and copy. Exact colors/type/spacing are in `04_DESIGN_TOKENS.md`.

Global chrome wraps all views:

## App shell

### Sidebar — 252px, `--surface`, right hairline. Top→bottom:
1. **Workspace header:** app logo (accent rounded square + white bar-chart glyph), "risr/crm" (800)
   over "Northwind Inc." (placeholder company), chevron.
2. **Space switcher** — label "SPACE" then two buttons: **Features** (cube icon, "Product development")
   and **Product Support** (headset icon, "Customer issues"). Active one has a filled accent icon tile
   + a small accent dot on the right. Switching space changes all data + which views make sense.
3. **Primary nav** — "Home" then group **PLANNING**: Board, Backlog, Timeline, List;
   group **INSIGHTS**: Reports, and **risr/crm AI** (sparkle icon, purple, "NEW" pill → opens AI panel).
   Active item = `--accent-soft` bg, `--accent` text.
4. **Footer:** "VIEW AS" segmented control **Developer | Product** (switches role → reshapes Home);
   current-user avatar chip (AL) + name + role label; theme toggle button (sun/moon).

### Top bar — 56px, `--surface`, bottom hairline:
- Breadcrumb: view title + `/` + space name (e.g. "Board / Features").
- Global search field (max ~400px): search icon, placeholder "Search issues, PRs, people…", `⌘K` hint.
- Right: **Filter** (on board/list/backlog only), **Ask AI** (purple outline → opens AI panel),
  **New** (accent filled, + icon).

---

## 1. Home — Developer dashboard (`role=developer`)
Max-width 1220px, centered. Header row: "Wednesday, July 8" eyebrow + "Good morning, Alex" (H1);
right = active-sprint chip (green dot, "Sprint 24", "6 days left · Jul 1 – 14").
Two-column grid **1.65fr / 1fr**:

**Left column:**
- **Your focus** card — issues assigned to the current user (not done). Each row: type badge, key
  (mono), title, optional BLOCKED pill, status pill, priority bars, points. Header shows count +
  "Assigned to you". Rows clickable → issue detail.
- **Review requests** card — PRs waiting on the current user. Row: author avatar, title, key + author
  name, PR # + CI dot, **Review** button (accent-soft).

**Right column:**
- **Your standup** (AI) — purple-tinted card, sparkle icon, "Drafted by risr/crm AI", 3–4 bullets,
  Copy / Post to Slack buttons, regenerate icon. Bullets come from `GET /api/dashboard`.
- **Your pull requests** — list of the user's PRs (state dot, title, branch mono, PR# + CI dot).
- **Sprint 24** health mini — big remaining-points number + committed, a segmented progress bar
  (done/review/in-progress), legend.

## 2. Home — Product Owner dashboard (`role=product_owner`)
Same header pattern but eyebrow = "Sprint 24 · Features" and H1 = the sprint goal. Grid **2fr / 1fr**:
- **Sprint health** (wide) — four big metrics: Committed, Completed (green), Remaining, "Scope added"
  (+2, amber); a 4-segment bar (done/review/in-progress/to-do) + legend; "On track" pill.
- **Weekly report** (AI, purple) — one-paragraph summary + "Generate full report" button (opens AI panel).
- **Risks flagged by AI** — list of at-risk issues each with a reason pill (e.g. "CI failing",
  "Blocked · unstarted", "Large · at risk", "Awaiting review 2d") + assignee avatar. Server derives these.
- **Team workload** — per-member horizontal bars of open story points; overloaded (≥13) bar turns red.
- **Epic progress** (full width) — per-feature progress bars (done/total points), rows link to the
  Feature's issue-detail. "View roadmap" link.

> Role switch persists and only changes Home. Board/Backlog/etc. are shared.

## 3. Board (Kanban)
Sticky sub-header: active-sprint dropdown (green dot + name), meta ("6 days left · 12/45 pts done"
for Features; "N open · M resolved" for Support), overlapping team avatars, "Group: Status".
Horizontal scroll row of **300px** columns: **To Do, In Progress, In Review, Done**. Column header:
status dot, UPPERCASE title, count, and a **WIP** indicator (`WIP n / limit`, turns red over limit;
limits To Do 6 / In Progress 4 / In Review 3 / Done none). Each column body is a drop zone; on
drag-over it highlights (accent-soft bg + dashed accent outline). "Add issue" ghost button at the bottom.

**Issue card:** type badge + key + optional BLOCKED pill; title (13.5px/500); label chips; if a PR
exists a mini PR strip (branch icon, PR#, CI dot); footer row = priority bars, points, comment count,
assignee avatar (or dashed unassigned circle). Cards are draggable (cursor grab; dragged card drops
to 0.35 opacity). **Features (epics) never appear on the board.**

## 4. Backlog / sprint planning
Max-width 1120px. Stacked collapsible groups:
- **Features space:** "Sprint 24" (active, green dot, "Start sprint" button, capacity bar `pts / 45`),
  "Sprint 25" (planning), "Backlog" (unscheduled). Capacity bar fills accent; over capacity → attention.
- **Support space:** "Needs triage", "Being worked", "Resolved".
Each group: chevron, name, meta, issue count, capacity (where relevant). Rows are dense: drag handle,
type badge, key, title, BLOCKED, labels, priority bars, points chip, PR#+CI dot, assignee. "Add issue"
row per group. Rows → issue detail. **Features excluded** from the lists (they're the containers).

## 5. List (table)
Sticky column header (Key / Title / Priority / Pts / PR). Rows grouped with a colored group header +
count. **First group = "Features"** (the epics, purple), each showing its child task tally; then groups
by status (In Progress, In Review, To Do, Done, Backlog). Row: drag handle, type badge, key, title,
labels, priority bars, points, PR#+CI dot, assignee. Whole row → issue detail (feature rows → feature detail).

## 6. Timeline (roadmap) — Features space only
Max-width 1180px. A month header (July/August/September) over a 12-week grid with a "Today" marker
(~week 1). One row per Feature: left label (color dot + name + "pts · % done"); right = a bar placed by
`startWeek`/`spanWeeks`, tinted in the feature color, with an inner fill showing progress. Rows clickable
→ feature detail. Legend below. In the Support space this view shows an empty state ("Support work is
triaged, not scheduled").

## 7. Reports & analytics
Max-width 1180px, stacked:
- **Stat cards** (4): Avg cycle time (2.4 days), Throughput (18 issues/sprint), PRs merged (6), Avg
  review time (5.2h) — each with a green delta pill.
- **Sprint burndown** — SVG line chart: dashed "ideal" line + solid accent "actual" line with a soft
  area fill, a "Today" vertical marker, y-axis labels (max/mid/0), x-axis (Jul 1 / Jul 8 / Jul 14).
- **Velocity** — 5-sprint grouped bars (committed = muted, completed = accent) with a legend.
- **Work distribution** — a single segmented bar (to-do/in-progress/review/done) + legend counts.
All numbers come from `GET /api/reports`.

## 8. Issue detail
Two-pane: main column (max ~840px) + **344px** right rail.

**Header:** Back button, breadcrumb "Space / KEY", "Create branch" + overflow. Then type badge + key,
title (H1), and a meta row of pills: status, priority (bars + label), points, feature chip.

**If the issue is a Feature (epic):** a **Tasks** card comes first — header "Tasks", "done/total done"
+ progress bar, "Add task"; each child row = completion check (circle→green check), type badge, key,
title, status pill, points. Rows → child detail.

**risr/crm AI card** (purple gradient), state machine:
- *Features issues* → primary **"Summarize thread"** button.
- *Support tickets* → primary **"Solve ticket with AI"** + secondary "Summarize thread", with the note
  "risr/crm AI diagnoses the ticket, writes the fix, and opens a pull request for review."
- *Loading* → spinner + "Reading N comments and the linked PR…".
- *Summarized* → 3–5 bullets + a "Suggested resolution" (summary + affected file chips) + **"Create PR
  with this fix"**.
- *Creating PR* → spinner "Writing the fix and opening a pull request…".
- *Done* → green success ("Opened PR #834 on cadence-ai/…-fix") + "what it changed" summary + files.

**Description** — headings, paragraphs, and bullet lists (rendered from the issue body).

**Development** card (GitHub) — header with a GitHub glyph. Shows the branch (name, "from main",
"+ahead/−behind"), then each linked PR: PR# + title + state pill (+ purple "AI" tag on AI PRs); a
mono stat strip (branch, +adds/−dels, files); and a CI checks list (build / unit tests / lint) with
pass/fail/pending icons. If no branch → "Create branch from this issue".

**Activity** — comments (avatar, name, time, body) interleaved with commit events ("pushed 3 commits
to <branch>"); a comment composer at the bottom (current-user avatar + input + Comment button).

**Right rail — Details:** Assignee, Reporter, Priority (bars), Points (mono), Sprint, **Feature**
(clickable chip → parent, present when the issue has a parent), Labels. **Reviewers** section below:
each reviewer avatar + name + state (approved/pending/changes with icon). "Request" link.

## risr/crm AI slide-over (global)
Right-anchored 414px panel over a scrim, slides in. Header: gradient sparkle tile, "risr/crm AI /
Context-aware assistant", close. Body: a context chip ("Looking at <view> · <space>"), "Try asking"
suggestion chips (Summarize this sprint / What's at risk? / Draft release notes / Find stale PRs), an
idle empty state, a busy spinner, and a done state (titled bullet list + Copy / Create report). Footer:
input + send. Opened from the sidebar "risr/crm AI", the top-bar "Ask AI", and dashboard AI buttons.
