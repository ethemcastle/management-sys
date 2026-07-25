import {
  ChangeDetectionStrategy,
  Component,
  computed,
  effect,
  inject,
  signal,
} from '@angular/core';
import { Router } from '@angular/router';

import { IssuesService } from '../../core/api/issues.service';
import { ViewsService } from '../../core/api/views.service';
import { BacklogGroup, Issue, Space, Status } from '../../core/models';
import { UiStore } from '../../core/stores/ui.store';
import { WorkspaceStore } from '../../core/stores/workspace.store';
import { MondayStore } from '../../core/stores/monday.store';
import { IssueRowComponent } from '../../shared/issue-row';
import { ProgressBarComponent } from '../../shared/progress-bar';

/** Backlog / sprint planning: stacked collapsible groups with capacity bars. */
@Component({
  selector: 'app-backlog',
  standalone: true,
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [IssueRowComponent, ProgressBarComponent],
  template: `
    <div class="view" style="max-width: 1120px;">
      <header class="head">
        <div>
          <div class="eyebrow">Planning</div>
          <h1 class="h1">Backlog</h1>
        </div>
      </header>

      <div class="groups">
        @for (g of filteredGroups(); track g.id) {
          @let collapsed = isCollapsed(g.id);
          <section class="card group">
            <div
              class="group-head"
              role="button"
              tabindex="0"
              [attr.aria-expanded]="!collapsed"
              (click)="toggle(g.id)"
              (keydown.enter)="toggle(g.id)"
              (keydown.space)="toggle(g.id); $event.preventDefault()"
            >
              <svg
                class="chevron"
                [class.open]="!collapsed"
                width="14"
                height="14"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                stroke-width="2.5"
                stroke-linecap="round"
                stroke-linejoin="round"
              >
                <polyline points="9 6 15 12 9 18" />
              </svg>

              <span class="name">{{ g.name }}</span>
              @if (g.active) { <span class="dot" title="Active sprint"></span> }
              <span class="meta">{{ g.meta }}</span>
              <span class="count mono">{{ g.count }}</span>

              <span class="spacer"></span>

              @if (g.active) {
                <button
                  type="button"
                  class="btn btn-accent start-btn"
                  (click)="startSprint(g, $event)"
                >
                  Start sprint
                </button>
              }

              @if (g.capacity; as capacity) {
                <span class="capacity">
                  <span class="cap-num mono" [class.over]="isOver(g)">
                    {{ g.points }} / {{ capacity }} pts
                  </span>
                  <span class="cap-bar">
                    <app-progress-bar
                      [value]="g.points"
                      [max]="capacity"
                      [color]="isOver(g) ? 'var(--danger)' : 'var(--accent)'"
                      [height]="6"
                    />
                  </span>
                </span>
              }
            </div>

            @if (!collapsed) {
              <div class="group-body">
                @for (i of g.issues; track i.key) {
                  <app-issue-row [issue]="i" (open)="go($event)" />
                } @empty {
                  <div class="no-issues">No issues</div>
                }

                @if (adding() === g.id) {
                  <input
                    class="add-input"
                    autofocus
                    placeholder="Issue title…"
                    [value]="addTitle()"
                    (click)="$event.stopPropagation()"
                    (input)="onAddInput($event)"
                    (keydown.enter)="submitAdd(g)"
                    (keydown.escape)="cancelAdd()"
                    (blur)="submitAdd(g)"
                  />
                } @else {
                  <button type="button" class="add-row" (click)="startAdd(g, $event)">
                    + Add issue
                  </button>
                }
              </div>
            }
          </section>
        } @empty {
          <div class="empty-state">No groups to plan.</div>
        }
      </div>
    </div>
  `,
  styles: [
    `
      .head {
        display: flex;
        align-items: flex-end;
        justify-content: space-between;
        margin-bottom: 18px;
      }
      .groups {
        display: flex;
        flex-direction: column;
        gap: 14px;
      }
      .group {
        overflow: hidden;
      }
      .group-head {
        display: flex;
        align-items: center;
        gap: 10px;
        width: 100%;
        padding: 13px 16px;
        background: transparent;
        border: none;
        font-family: inherit;
        text-align: left;
        cursor: pointer;
        color: var(--text);
        transition: background 0.12s ease;
      }
      .group-head:hover {
        background: var(--surface-2);
      }
      .chevron {
        color: var(--text-3);
        flex-shrink: 0;
        transition: transform 0.18s ease;
      }
      .chevron.open {
        transform: rotate(90deg);
      }
      .name {
        font-size: 14px;
        font-weight: 700;
        color: var(--text);
        flex-shrink: 0;
      }
      .dot {
        width: 7px;
        height: 7px;
        border-radius: 50%;
        background: var(--success);
        flex-shrink: 0;
      }
      .meta {
        font-size: 12px;
        font-weight: 500;
        color: var(--text-3);
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
        min-width: 0;
      }
      .count {
        font-size: 11.5px;
        font-weight: 600;
        color: var(--text-3);
        flex-shrink: 0;
      }
      .spacer {
        flex: 1;
      }
      .start-btn {
        padding: 5px 11px;
        font-size: 12px;
        flex-shrink: 0;
      }
      .capacity {
        display: flex;
        align-items: center;
        gap: 10px;
        flex-shrink: 0;
      }
      .cap-num {
        font-size: 11.5px;
        font-weight: 600;
        color: var(--text-2);
        white-space: nowrap;
      }
      .cap-num.over {
        color: var(--danger);
      }
      .cap-bar {
        display: block;
        width: 120px;
      }
      .group-body {
        border-top: 1px solid var(--border);
      }
      .no-issues {
        padding: 14px 16px;
        font-size: 12.5px;
        color: var(--text-3);
        border-bottom: 1px solid var(--border);
      }
      .add-row {
        display: block;
        width: 100%;
        padding: 9px 14px;
        background: transparent;
        border: 1.5px dashed var(--border-2);
        border-radius: 0;
        font-family: inherit;
        font-size: 12.5px;
        font-weight: 500;
        color: var(--text-3);
        text-align: left;
        cursor: pointer;
        transition:
          color 0.12s ease,
          background 0.12s ease;
      }
      .add-row:hover {
        color: var(--text-2);
        background: var(--surface-2);
      }
      .add-input {
        display: block;
        width: 100%;
        padding: 10px 16px;
        border: none;
        border-top: 1px solid var(--accent-line);
        background: var(--surface);
        color: var(--text);
        font-family: inherit;
        font-size: 13px;
        outline: none;
      }
    `,
  ],
})
export class BacklogComponent {
  private views = inject(ViewsService);
  private issues = inject(IssuesService);
  private router = inject(Router);
  private ws = inject(WorkspaceStore);
  private monday = inject(MondayStore);
  private ui = inject(UiStore);

  private readonly groups = signal<BacklogGroup[]>([]);
  private readonly collapsed = signal<Set<string>>(new Set());
  readonly adding = signal<string | null>(null);
  readonly addTitle = signal('');

  /** Groups with each list filtered by the global search + "only mine" toggle. */
  readonly filteredGroups = computed<BacklogGroup[]>(() => {
    const term = this.ui.search().trim().toLowerCase();
    const mineOnly = this.ui.onlyMine();
    const mine = this.ws.currentUser()?.initials ?? null;

    return this.groups().map((g) => {
      const issues = g.issues.filter((i) => this.matches(i, term, mineOnly, mine));
      return { ...g, issues, count: issues.length };
    });
  });

  constructor() {
    effect(() => {
      const space = this.ws.space();
      this.monday.syncTick();
      this.load(space);
    });
  }

  private matches(
    issue: Issue,
    term: string,
    mineOnly: boolean,
    mine: string | null,
  ): boolean {
    if (mineOnly && issue.assignee?.initials !== mine) return false;
    if (!term) return true;
    return (
      issue.title.toLowerCase().includes(term) ||
      issue.key.toLowerCase().includes(term)
    );
  }

  private load(space: Space): void {
    this.views.backlog(space).subscribe((b) => {
      this.groups.set(b.groups);
      // Default: all groups expanded.
      this.collapsed.set(new Set());
    });
  }

  isCollapsed(id: string): boolean {
    return this.collapsed().has(id);
  }

  toggle(id: string): void {
    this.collapsed.update((prev) => {
      const next = new Set(prev);
      if (next.has(id)) {
        next.delete(id);
      } else {
        next.add(id);
      }
      return next;
    });
  }

  isOver(group: BacklogGroup): boolean {
    return group.capacity !== null && group.points > group.capacity;
  }

  go(key: string): void {
    this.router.navigate(['/issues', key]);
  }

  startSprint(group: BacklogGroup, event: Event): void {
    event.stopPropagation();
    this.views.startSprint(group.id).subscribe(() => {
      this.ws.refreshSprints();
      this.load(this.ws.space());
    });
  }

  startAdd(group: BacklogGroup, event: Event): void {
    event.stopPropagation();
    this.adding.set(group.id);
    this.addTitle.set('');
  }
  cancelAdd(): void {
    this.adding.set(null);
    this.addTitle.set('');
  }
  onAddInput(e: Event): void {
    this.addTitle.set((e.target as HTMLInputElement).value);
  }
  submitAdd(group: BacklogGroup): void {
    const title = this.addTitle().trim();
    if (!title) {
      this.cancelAdd();
      return;
    }
    const space = this.ws.space();
    let sprintId: string | null = null;
    let status: Status = 'todo';
    if (space === 'features') {
      sprintId = group.id === 'backlog' ? null : group.id;
      status = group.id === 'backlog' ? 'backlog' : 'todo';
    } else {
      status = group.id === 'working' ? 'inprogress' : group.id === 'resolved' ? 'done' : 'todo';
    }
    this.issues
      .create({ type: 'task', title, space, status, sprintId, priority: 1, points: 0 })
      .subscribe(() => {
        this.cancelAdd();
        this.load(space);
      });
  }
}
