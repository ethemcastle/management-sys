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
import { Issue, Space, Status } from '../../core/models';
import { STATUS_META, TYPE_META } from '../../core/theme';
import { UiStore } from '../../core/stores/ui.store';
import { WorkspaceStore } from '../../core/stores/workspace.store';
import { MondayStore } from '../../core/stores/monday.store';
import { IssueRowComponent } from '../../shared/issue-row';
import { TypeBadgeComponent } from '../../shared/type-badge';

/** A colored, collapsible-free section of rows in the List view. */
interface ListGroup {
  id: string;
  label: string;
  color: string;
  count: number;
  /** Feature (epic) rows render inline; regular issues use app-issue-row. */
  features: { issue: Issue; tally: string }[];
  issues: Issue[];
}

/** Order the status buckets appear below the Features group. */
const STATUS_ORDER: Status[] = ['inprogress', 'review', 'todo', 'done', 'backlog'];

/** List (table) view: features first, then issues grouped by status. */
@Component({
  selector: 'app-list',
  standalone: true,
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [IssueRowComponent, TypeBadgeComponent],
  template: `
    <div class="view" style="max-width: 1180px;">
      <header class="head">
        <div>
          <div class="eyebrow">{{ spaceName() }}</div>
          <h1 class="h1">List</h1>
        </div>
      </header>

      @if (groups().length === 0) {
        <div class="empty-state">No issues in this view.</div>
      } @else {
        <div class="card table">
          <div class="col-head">
            <span class="ch-key micro">Key</span>
            <span class="ch-title micro">Title</span>
            <span class="ch-spacer"></span>
            <span class="ch-prio micro">Priority</span>
            <span class="ch-pts micro">Pts</span>
            <span class="ch-pr micro">PR</span>
            <span class="ch-assignee"></span>
          </div>

          @for (g of groups(); track g.id) {
            <section class="group">
              <div class="group-head" [style.borderLeftColor]="g.color">
                <span class="dot" [style.background]="g.color"></span>
                <span class="group-label">{{ g.label }}</span>
                <span class="group-count mono">{{ g.count }}</span>
              </div>

              @for (f of g.features; track f.issue.key) {
                <div class="feature-row" (click)="go(f.issue.key)">
                  <app-type-badge [type]="f.issue.type" [size]="18" />
                  <span class="fr-key mono">{{ f.issue.key }}</span>
                  <span class="fr-title">{{ f.issue.title }}</span>
                  <span class="fr-spacer"></span>
                  <span class="fr-tally">{{ f.tally }}</span>
                </div>
              }

              @for (i of g.issues; track i.key) {
                <app-issue-row [issue]="i" (open)="go($event)" />
              }
            </section>
          }
        </div>
      }
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
      .table {
        overflow: hidden;
      }
      .col-head {
        position: sticky;
        top: 0;
        z-index: 5;
        display: flex;
        align-items: center;
        gap: 11px;
        padding: 8px 14px;
        background: var(--surface-2);
        border-bottom: 1px solid var(--border);
      }
      /* Mirror app-issue-row's flex layout so labels align with the columns. */
      .ch-key {
        width: 58px;
        flex-shrink: 0;
        padding-left: 29px;
      }
      .ch-title {
        flex: 0 1 auto;
      }
      .ch-spacer {
        flex: 1;
      }
      .ch-prio {
        flex-shrink: 0;
      }
      .ch-pts {
        width: 18px;
        text-align: right;
        flex-shrink: 0;
      }
      .ch-pr {
        width: 62px;
        flex-shrink: 0;
      }
      .ch-assignee {
        width: 24px;
        flex-shrink: 0;
      }

      .group-head {
        display: flex;
        align-items: center;
        gap: 8px;
        padding: 7px 14px 7px 12px;
        border-left: 2px solid var(--border-2);
        background: var(--surface-2);
        border-bottom: 1px solid var(--border);
      }
      .group + .group .group-head {
        border-top: 1px solid var(--border);
      }
      .dot {
        width: 7px;
        height: 7px;
        border-radius: 50%;
        flex-shrink: 0;
      }
      .group-label {
        font-size: 11px;
        font-weight: 700;
        letter-spacing: 0.05em;
        text-transform: uppercase;
        color: var(--text-2);
      }
      .group-count {
        font-size: 11px;
        font-weight: 600;
        color: var(--text-3);
      }

      .feature-row {
        display: flex;
        align-items: center;
        gap: 11px;
        padding: 9px 14px;
        cursor: pointer;
        border-bottom: 1px solid var(--border);
        transition: background 0.12s ease;
      }
      .feature-row:hover {
        background: var(--surface-2);
      }
      .fr-key {
        font-size: 11.5px;
        color: var(--text-3);
        font-weight: 500;
        flex-shrink: 0;
        width: 58px;
      }
      .fr-title {
        font-size: 13.5px;
        font-weight: 500;
        color: var(--text);
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
        min-width: 0;
      }
      .fr-spacer {
        flex: 1;
      }
      .fr-tally {
        font-size: 11.5px;
        font-weight: 600;
        color: var(--text-3);
        flex-shrink: 0;
      }
    `,
  ],
})
export class ListComponent {
  private issues = inject(IssuesService);
  private ws = inject(WorkspaceStore);
  private monday = inject(MondayStore);
  private ui = inject(UiStore);
  private router = inject(Router);

  private readonly all = signal<Issue[]>([]);

  readonly spaceName = computed(() => this.ws.spaceInfo()?.name ?? 'Features');

  /** Search + "only mine" applied, then split into Features + status groups. */
  readonly groups = computed<ListGroup[]>(() => {
    const filtered = this.filtered();
    if (filtered.length === 0) return [];

    const groups: ListGroup[] = [];
    const epics = filtered.filter((i) => i.type === 'epic');
    const rest = filtered.filter((i) => i.type !== 'epic');

    // 1. Features group first (all epics), each with a child-task tally.
    if (epics.length > 0) {
      groups.push({
        id: 'features',
        label: 'Features',
        color: TYPE_META['epic'].color,
        count: epics.length,
        features: epics.map((e) => ({ issue: e, tally: this.tallyFor(e, rest) })),
        issues: [],
      });
    }

    // 2. Then non-epic issues grouped by status, in the spec's order.
    for (const status of STATUS_ORDER) {
      const inGroup = rest.filter((i) => i.status === status);
      if (inGroup.length === 0) continue;
      const meta = STATUS_META[status];
      groups.push({
        id: status,
        label: meta.label,
        color: meta.color,
        count: inGroup.length,
        features: [],
        issues: inGroup,
      });
    }

    return groups;
  });

  private readonly filtered = computed<Issue[]>(() => {
    let list = this.all();

    const q = this.ui.search().trim().toLowerCase();
    if (q) {
      list = list.filter(
        (i) =>
          i.title.toLowerCase().includes(q) || i.key.toLowerCase().includes(q),
      );
    }

    if (this.ui.onlyMine()) {
      const me = this.ws.currentUser()?.initials;
      list = list.filter((i) => !!me && i.assignee?.initials === me);
    }

    return list;
  });

  constructor() {
    // Reload whenever the active space changes.
    effect(() => {
      const space = this.ws.space();
      this.monday.syncTick();
      this.load(space);
    });
  }

  private load(space: Space): void {
    this.issues.list({ space, includeFeatures: true }).subscribe((issues) => {
      this.all.set(issues);
    });
  }

  /** "N task(s)" — child issues (non-epic) whose feature points at this epic. */
  private tallyFor(epic: Issue, rest: Issue[]): string {
    const n = rest.filter((i) => i.feature?.key === epic.key).length;
    return `${n} ${n === 1 ? 'task' : 'tasks'}`;
  }

  go(key: string): void {
    this.router.navigate(['/issues', key]);
  }
}
