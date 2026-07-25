# 03 · API Contract

REST API for Cadence (FastAPI). All responses are JSON, camelCase (configure Pydantic to alias
snake→camel). Base path `/api`. Issues are addressed by their **key** (`CAD-142`), not a numeric id.

Query params shared by list endpoints: `space` (`features|support`, required for board/backlog/list),
`sprint` (id), `assignee` (initials).

---

## Meta / bootstrap

```
GET /api/bootstrap
→ { currentUser, members[], spaces[], sprints[], labels{} }        # everything static the shell needs
```

## Issues

```
GET  /api/issues?space=features&sprint=s24&status=inprogress
→ Issue[]                                    # denormalized (see 02_DATA_MODEL.md), excludes type=epic unless includeFeatures=true

GET  /api/issues/{key}
→ IssueDetail                                # full issue incl. description blocks, comments[], pr, reviewers[]
                                             # if type=epic → also children[] + childProgress{done,total}
                                             # if child   → feature{key,title,color}

POST /api/issues
body { type, title, priority, status?, space, points?, assigneeInitials?, featureKey?, sprintId?, labels[] }
→ Issue                                       # "New" button

PATCH /api/issues/{key}
body (any subset) { status?, assigneeInitials?, priority?, points?, sprintId?, featureKey?, title?, blocked? }
→ Issue                                       # used by drag-and-drop (status), backlog moves (sprintId), etc.

POST /api/issues/{key}/branch
→ { branch: "feat/cad-142-...", issue }       # "Create branch" — generates a branch name from the key+title
```

### Board / Backlog / metrics (server computes the groupings & numbers the UI shows)

```
GET /api/board?space=features&sprint=s24
→ { columns: [ { key:"todo", title:"To Do", wipLimit:6, count, issues:Issue[] },
               { key:"inprogress", wipLimit:4, ... }, { key:"review", wipLimit:3, ... },
               { key:"done", wipLimit:0, ... } ] }
# Features (type=epic) are excluded from the board. wipLimit 0 = no limit.

GET /api/backlog?space=features
# For features space: groups = active sprint, next sprint (planning), Backlog (unscheduled).
# For support space: groups = Needs triage (todo), Being worked (inprogress+review), Resolved (done).
→ { groups: [ { id, name, meta, active, capacity, points, count, issues:Issue[] } ] }

GET /api/sprints/{id}/health?space=features
→ { committed, done, inProgress, review, todo,           # story points per bucket
    remaining, scopeAdded, onTrack:true }

GET /api/reports?space=features&sprint=s24
→ { stats:[ {label,value,unit,delta,good} ],             # cycle time, throughput, PRs merged, review time
    burndown:{ max, ideal:number[], actual:number[], days:[...] },
    velocity:[ {sprint:"S24", committed, completed} ],
    distribution:[ {status, label, count} ] }

GET /api/timeline?space=features
→ { months:[{label,startWeek,spanWeeks}], todayWeek, rows:[ {featureKey, name, color, startWeek, spanWeeks, progress} ] }

GET /api/dashboard?role=developer   (or role=product_owner)
# Developer: { myFocus:Issue[], reviewQueue:Issue[], myPrs:Issue[], standup:string[] (AI), sprintHealth }
# PO:        { sprintHealth, risks:Issue[]+reason, workload:[{member,points}], epicProgress:[...], weeklyReport:string }
```

## Comments

```
POST /api/issues/{key}/comments   body { body }   → Comment
```

---

## AI endpoints (the differentiator)

Back these with an `AiService` interface. Ship a **`MockAiService`** that returns deterministic,
correctly-shaped responses so the UI is fully demoable without a model. Keep a seam to plug a real
LLM in later. These endpoints simulate latency in the prototype (~1.5–2s) — the frontend shows a
loading state, so a real 1–3s response is fine.

```
POST /api/ai/issues/{key}/summarize
→ { bullets: string[],                        # 3–5 short catch-up bullets about the thread + PR + reviews
    suggestedResolution: { summary: string, files: string[] } }   # shown as "Suggested resolution"

POST /api/ai/issues/{key}/create-pr
# "Create PR with this fix" (from a summarized issue) OR the support "Solve ticket with AI".
# Creates an AI-authored PR row (aiGenerated=true, state=open, checks=pending) linked to the issue.
→ { pr: PullRequest,                          # num e.g. 834, branch "cadence-ai/cad-142-fix"
    issue: Issue }                            # PR now appears in the issue's Development section

POST /api/ai/tickets/{key}/solve
# Support-space convenience = summarize+diagnose+create-PR in one call. Returns the PR plus the
# "what it changed" summary the UI renders inline.
→ { pr: PullRequest, summary: string, files: string[], issue: Issue }

POST /api/ai/assistant
body { question: string, context: { view, space, sprint? } }
→ { bullets: string[] }                       # the Cadence AI slide-over panel answer
```

### AI response content (mock guidance)
- **summarize** bullets should reference real fields of the issue (who scoped it, branch/PR state,
  CI status, reviewer notes, a "net: …" closer). See the prototype's issue detail for tone/length.
- **create-pr / solve** must actually persist a new `PullRequest` (aiGenerated=true) so the issue's
  Development section and the board/list PR badges update. Branch = `cadence-ai/{key-lower}-fix`,
  first PR number after the max in seed (e.g. 834).

---

## Conventions
- **Errors:** FastAPI default problem shape; 404 for unknown key, 409 if a PATCH would break a WIP
  limit only if you choose to enforce server-side (the prototype enforces WIP visually, not as a hard block).
- **camelCase** everywhere in JSON (Pydantic `alias_generator=to_camel`, `populate_by_name=True`).
- **CORS:** allow the Angular dev origin.
- **OpenAPI:** FastAPI auto-serves `/docs`; hand that to the frontend dev as the live contract.
