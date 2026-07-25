import { ChangeDetectionStrategy, Component, computed, effect, inject, signal, untracked } from '@angular/core';
import { Router } from '@angular/router';

import { IssuesService } from '../core/api/issues.service';
import { Issue, IssueType, MondayGroup, Space, Status } from '../core/models';
import { PRIORITY_META, STATUS_META, TYPE_META, softFill } from '../core/theme';
import { MondayStore } from '../core/stores/monday.store';
import { UiStore } from '../core/stores/ui.store';
import { WorkspaceStore } from '../core/stores/workspace.store';
import { TypeBadgeComponent } from '../shared/type-badge';

@Component({
  selector: 'app-new-issue-modal',
  standalone: true,
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [TypeBadgeComponent],
  template: `
    @if (ui.newIssueOpen()) {
      <div class="scrim" (click)="close()"></div>
      <div class="modal" role="dialog" aria-label="New ticket">
        <div class="mhead">
          <span class="mtitle">New ticket</span>
          <button class="x" (click)="close()" aria-label="Close">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round"><path d="M6 6l12 12M18 6L6 18" /></svg>
          </button>
        </div>

        <div class="mbody">
          <!-- Type -->
          <div class="field">
            <label>Type</label>
            <div class="seg">
              @for (t of TYPES; track t) {
                <button class="seg-btn" [class.on]="ftype() === t" (click)="ftype.set(t)">
                  <app-type-badge [type]="t" [size]="16" />{{ typeMeta[t] ? cap(t) : t }}
                </button>
              }
            </div>
          </div>

          <!-- Title -->
          <div class="field">
            <label>Title</label>
            <input class="in" autofocus placeholder="What needs doing?" [value]="title()"
              (input)="title.set($any($event.target).value)" (keydown.enter)="create()" />
          </div>

          <!-- Description -->
          <div class="field">
            <label>Description</label>
            <textarea class="in ta" rows="3" placeholder="Add more detail (optional)…"
              [value]="description()" (input)="description.set($any($event.target).value)"></textarea>
          </div>

          <div class="row2">
            <div class="field">
              <label>Space</label>
              <div class="seg">
                <button class="seg-btn" [class.on]="space() === 'features'" (click)="setSpace('features')">Features</button>
                <button class="seg-btn" [class.on]="space() === 'support'" (click)="setSpace('support')">Support</button>
              </div>
            </div>
            <div class="field">
              <label>Priority</label>
              <select class="in" (change)="priority.set(+$any($event.target).value)">
                @for (p of PRIORITIES; track p) {
                  <option [value]="p" [selected]="priority() === p">{{ priorityMeta[p].label }}</option>
                }
              </select>
            </div>
          </div>

          <div class="row2">
            <div class="field">
              <label>Status</label>
              <select class="in" (change)="status.set($any($event.target).value)">
                @for (s of STATUSES; track s) {
                  <option [value]="s" [selected]="status() === s">{{ statusMeta[s].label }}</option>
                }
              </select>
            </div>
            <div class="field">
              <label>Points</label>
              <input class="in" type="number" min="0" [value]="points()" (input)="points.set(+$any($event.target).value || 0)" />
            </div>
          </div>

          <div class="row2">
            <div class="field">
              <label>Assignee</label>
              <select class="in" (change)="assignee.set($any($event.target).value)">
                <option value="" [selected]="!assignee()">Unassigned</option>
                @for (m of ws.members(); track m.initials) {
                  <option [value]="m.initials" [selected]="assignee() === m.initials">{{ m.name }}</option>
                }
              </select>
            </div>
            @if (space() === 'features') {
              <div class="field">
                <label>Sprint</label>
                <select class="in" (change)="sprintId.set($any($event.target).value)">
                  <option value="" [selected]="!sprintId()">No sprint</option>
                  @for (s of ws.sprints(); track s.id) {
                    <option [value]="s.id" [selected]="sprintId() === s.id">{{ s.name }}</option>
                  }
                </select>
              </div>
            }
          </div>

          @if (monday.connected() && space() === 'features') {
            <div class="row2">
              <div class="field">
                <label>monday board</label>
                <select class="in" (change)="setBoard($any($event.target).value)">
                  @for (b of monday.boards(); track b.boardId) {
                    <option [value]="b.boardId" [selected]="mondayBoardId() === b.boardId">{{ b.name }}</option>
                  }
                  <option value="" [selected]="!mondayBoardId()">— Don't create in monday —</option>
                </select>
              </div>
              @if (mondayBoardId()) {
                <div class="field">
                  <label>Group</label>
                  <select class="in" (change)="mondayGroupId.set($any($event.target).value)">
                    @for (g of mondayGroups(); track g.id) {
                      <option [value]="g.id" [selected]="mondayGroupId() === g.id">{{ g.title }}</option>
                    }
                  </select>
                </div>
              }
            </div>
            @if (mondayBoardId()) {
              <div class="hint">Creates a matching item on this monday board &amp; group.</div>
            }
          }

          @if (space() === 'features' && epics().length) {
            <div class="field">
              <label>Feature</label>
              <select class="in" (change)="featureKey.set($any($event.target).value)">
                <option value="" [selected]="!featureKey()">None</option>
                @for (e of epics(); track e.key) {
                  <option [value]="e.key" [selected]="featureKey() === e.key">{{ e.key }} · {{ e.title }}</option>
                }
              </select>
            </div>
          }

          <div class="field">
            <label>Labels</label>
            <div class="labels">
              @for (l of labelList(); track l.name) {
                <button class="lchip" [class.on]="labels().has(l.name)"
                  [style.color]="labels().has(l.name) ? l.color : 'var(--text-2)'"
                  [style.background]="labels().has(l.name) ? softFill(l.color, 14) : 'var(--surface-2)'"
                  [style.borderColor]="labels().has(l.name) ? softFill(l.color, 30) : 'var(--border)'"
                  (click)="toggleLabel(l.name)">{{ l.name }}</button>
              }
            </div>
          </div>
        </div>

        <div class="mfoot">
          <button class="btn" (click)="close()">Cancel</button>
          <button class="btn btn-accent" [disabled]="!title().trim() || saving()" (click)="create()">
            {{ saving() ? 'Creating…' : 'Create ticket' }}
          </button>
        </div>
      </div>
    }
  `,
  styles: [
    `
      .scrim {
        position: fixed;
        inset: 0;
        background: rgba(0, 0, 0, 0.38);
        z-index: 50;
      }
      .modal {
        position: fixed;
        top: 50%;
        left: 50%;
        transform: translate(-50%, -50%);
        width: 540px;
        max-width: 94vw;
        max-height: 90vh;
        overflow: hidden;
        background: var(--surface);
        border: 1px solid var(--border);
        border-radius: 14px;
        box-shadow: var(--shadow-pop);
        z-index: 51;
        display: flex;
        flex-direction: column;
        /* opacity-only so it doesn't clobber the centering transform */
        animation: cadModalIn 0.18s ease both;
      }
      @keyframes cadModalIn {
        from {
          opacity: 0;
        }
        to {
          opacity: 1;
        }
      }
      .mhead {
        display: flex;
        align-items: center;
        padding: 15px 18px;
        border-bottom: 1px solid var(--border);
      }
      .mtitle {
        font-size: 15.5px;
        font-weight: 700;
        color: var(--text);
        flex: 1;
      }
      .x {
        border: none;
        background: transparent;
        color: var(--text-3);
        cursor: pointer;
        padding: 4px;
        border-radius: 6px;
      }
      .x:hover {
        background: var(--surface-2);
        color: var(--text);
      }
      .mbody {
        padding: 16px 18px;
        overflow-y: auto;
        display: flex;
        flex-direction: column;
        gap: 13px;
      }
      .field {
        display: flex;
        flex-direction: column;
        gap: 6px;
        flex: 1;
        min-width: 0;
      }
      .field > label {
        font-size: 11px;
        font-weight: 700;
        letter-spacing: 0.05em;
        text-transform: uppercase;
        color: var(--text-3);
      }
      .row2 {
        display: flex;
        gap: 12px;
      }
      .in {
        border: 1px solid var(--border);
        background: var(--surface-2);
        color: var(--text);
        border-radius: 9px;
        padding: 9px 11px;
        font-size: 13.5px;
        font-family: inherit;
        outline: none;
        width: 100%;
      }
      .in:focus {
        border-color: var(--accent-line);
      }
      .ta {
        resize: vertical;
        min-height: 62px;
        line-height: 1.45;
      }
      .seg {
        display: flex;
        gap: 6px;
      }
      .seg-btn {
        display: inline-flex;
        align-items: center;
        gap: 6px;
        padding: 8px 12px;
        border: 1px solid var(--border);
        background: var(--surface);
        color: var(--text-2);
        border-radius: 9px;
        font-size: 13px;
        font-weight: 600;
        cursor: pointer;
        font-family: inherit;
        flex: 1;
        justify-content: center;
      }
      .seg-btn:hover {
        border-color: var(--border-2);
      }
      .seg-btn.on {
        border-color: var(--accent-line);
        background: var(--accent-soft);
        color: var(--accent);
      }
      .hint {
        font-size: 11.5px;
        color: var(--text-3);
        margin-top: -4px;
      }
      .labels {
        display: flex;
        flex-wrap: wrap;
        gap: 6px;
      }
      .lchip {
        padding: 4px 10px;
        border: 1px solid var(--border);
        border-radius: 7px;
        font-size: 12px;
        font-weight: 600;
        cursor: pointer;
        font-family: inherit;
      }
      .mfoot {
        display: flex;
        justify-content: flex-end;
        gap: 9px;
        padding: 13px 18px;
        border-top: 1px solid var(--border);
      }
      .mfoot .btn[disabled] {
        opacity: 0.5;
        cursor: not-allowed;
      }
    `,
  ],
})
export class NewIssueModalComponent {
  readonly ui = inject(UiStore);
  readonly ws = inject(WorkspaceStore);
  readonly monday = inject(MondayStore);
  private issues = inject(IssuesService);
  private router = inject(Router);

  readonly TYPES: IssueType[] = ['story', 'bug', 'task'];
  readonly STATUSES: Status[] = ['backlog', 'todo', 'inprogress', 'review', 'done'];
  readonly PRIORITIES = [0, 1, 2, 3];
  readonly priorityMeta = PRIORITY_META;
  readonly statusMeta = STATUS_META;
  readonly typeMeta = TYPE_META;
  readonly softFill = softFill;

  readonly ftype = signal<IssueType>('task');
  readonly title = signal('');
  readonly description = signal('');
  readonly space = signal<Space>('features');
  readonly priority = signal(1);
  readonly status = signal<Status>('backlog');
  readonly points = signal(0);
  readonly assignee = signal('');
  readonly sprintId = signal('');
  readonly featureKey = signal('');
  readonly labels = signal<Set<string>>(new Set());
  readonly epics = signal<Issue[]>([]);
  readonly saving = signal(false);
  readonly mondayBoardId = signal('');
  readonly mondayGroupId = signal('');

  readonly labelList = computed(() =>
    Object.entries(this.ws.labels()).map(([name, color]) => ({ name, color })),
  );
  readonly mondayGroups = computed<MondayGroup[]>(
    () => this.monday.boards().find((b) => b.boardId === this.mondayBoardId())?.groups ?? [],
  );

  setBoard(id: string) {
    this.mondayBoardId.set(id);
    const b = this.monday.boards().find((x) => x.boardId === id);
    this.mondayGroupId.set(b?.groups?.[0]?.id ?? '');
  }

  constructor() {
    effect(() => {
      if (this.ui.newIssueOpen()) {
        untracked(() => {
          this.initForm();
          this.loadEpics();
        });
      }
    });
  }

  private initForm() {
    const p = this.ui.newIssuePrefill();
    this.ftype.set('task');
    this.title.set('');
    this.description.set('');
    this.space.set(p?.space ?? this.ws.space());
    this.priority.set(1);
    this.status.set(p?.status ?? 'backlog');
    this.points.set(0);
    this.assignee.set('');
    this.sprintId.set(p?.sprintId ?? '');
    this.featureKey.set(p?.featureKey ?? '');
    this.labels.set(new Set());
    this.saving.set(false);
    // Default the monday target to the first board + its first group.
    const b0 = this.monday.boards()[0];
    this.mondayBoardId.set(b0?.boardId ?? '');
    this.mondayGroupId.set(b0?.groups?.[0]?.id ?? '');
  }

  private loadEpics() {
    this.issues.list({ space: this.space(), includeFeatures: true }).subscribe((all) => {
      this.epics.set(all.filter((i) => i.type === 'epic'));
    });
  }

  setSpace(s: Space) {
    this.space.set(s);
    this.featureKey.set('');
    if (s === 'support') this.sprintId.set('');
    this.loadEpics();
  }

  toggleLabel(name: string) {
    this.labels.update((set) => {
      const next = new Set(set);
      next.has(name) ? next.delete(name) : next.add(name);
      return next;
    });
  }

  cap(t: string): string {
    return t.charAt(0).toUpperCase() + t.slice(1);
  }

  close() {
    this.ui.closeNewIssue();
  }

  create() {
    const title = this.title().trim();
    if (!title || this.saving()) return;
    this.saving.set(true);
    // Create in monday only for features tickets with a board chosen.
    const useMonday = this.space() === 'features' && !!this.mondayBoardId();
    const board = useMonday
      ? this.monday.boards().find((b) => b.boardId === this.mondayBoardId())
      : undefined;
    this.issues
      .create({
        type: this.ftype(),
        title,
        description: this.description().trim() || null,
        priority: this.priority(),
        status: this.status(),
        space: this.space(),
        points: this.points(),
        assigneeInitials: this.assignee() || null,
        featureKey: this.featureKey() || null,
        sprintId: this.sprintId() || null,
        labels: [...this.labels()],
        product: board?.name ?? null,
        mondayBoardId: useMonday ? this.mondayBoardId() : null,
        mondayGroupId: useMonday ? this.mondayGroupId() || null : null,
      })
      .subscribe({
        next: (issue) => {
          this.monday.refresh(); // reflect the new item on the monday page
          this.close();
          this.router.navigate(['/issues', issue.key]);
        },
        error: () => this.saving.set(false),
      });
  }
}
