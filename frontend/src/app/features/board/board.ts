import {
  CdkDragDrop,
  DragDropModule,
  moveItemInArray,
  transferArrayItem,
} from '@angular/cdk/drag-drop';
import { ChangeDetectionStrategy, Component, computed, effect, inject, signal } from '@angular/core';
import { Router } from '@angular/router';

import { IssuesService } from '../../core/api/issues.service';
import { ViewsService } from '../../core/api/views.service';
import { BoardColumn, Issue, Status } from '../../core/models';
import { STATUS_META } from '../../core/theme';
import { MondayStore } from '../../core/stores/monday.store';
import { WorkspaceStore } from '../../core/stores/workspace.store';
import { IssueCardComponent } from '../../shared/issue-card';

@Component({
  selector: 'app-board',
  standalone: true,
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [DragDropModule, IssueCardComponent],
  templateUrl: './board.html',
  styleUrl: './board.scss',
})
export class BoardComponent {
  private views = inject(ViewsService);
  private issues = inject(IssuesService);
  private router = inject(Router);
  readonly ws = inject(WorkspaceStore);
  private monday = inject(MondayStore);

  readonly columns = signal<BoardColumn[]>([]);
  readonly loading = signal(true);
  readonly dragOver = signal<Status | null>(null);
  readonly adding = signal<Status | null>(null);
  readonly addTitle = signal('');

  readonly statusMeta = STATUS_META;

  // header meta line
  readonly meta = computed(() => {
    const cols = this.columns();
    if (this.ws.space() === 'support') {
      const open = this.count(cols, ['todo', 'inprogress', 'review']);
      const resolved = this.count(cols, ['done']);
      return `${open} open · ${resolved} resolved`;
    }
    const done = this.points(cols, 'done');
    const cap = this.ws.activeSprint()?.capacity ?? 0;
    const left = this.ws.activeSprint()?.daysLeft;
    const leftTxt = left != null ? `${left} days left · ` : '';
    return `${leftTxt}${done}/${cap} pts done`;
  });

  readonly headerAvatars = computed(() => this.ws.members().slice(0, 5));

  constructor() {
    effect(() => {
      const space = this.ws.space();
      const sprint = space === 'features' ? this.ws.activeSprint()?.id : undefined;
      this.monday.syncTick(); // reload the board after a monday Sync
      this.load(space, sprint);
    });
  }

  private load(space: 'features' | 'support', sprint?: string) {
    this.loading.set(true);
    this.views.board(space, sprint).subscribe((b) => {
      this.columns.set(b.columns);
      this.loading.set(false);
    });
  }

  private count(cols: BoardColumn[], keys: Status[]): number {
    return cols.filter((c) => keys.includes(c.key)).reduce((n, c) => n + c.issues.length, 0);
  }
  private points(cols: BoardColumn[], key: Status): number {
    const c = cols.find((x) => x.key === key);
    return c ? c.issues.reduce((n, i) => n + i.points, 0) : 0;
  }

  over(col: BoardColumn): boolean {
    const c = col.issues.length;
    return col.wipLimit > 0 && c > col.wipLimit;
  }

  go(key: string) {
    this.router.navigate(['/issues', key]);
  }

  startAdd(status: Status) {
    this.adding.set(status);
    this.addTitle.set('');
  }
  cancelAdd() {
    this.adding.set(null);
    this.addTitle.set('');
  }
  onAddInput(e: Event) {
    this.addTitle.set((e.target as HTMLInputElement).value);
  }
  submitAdd(status: Status) {
    const title = this.addTitle().trim();
    if (!title) {
      this.cancelAdd();
      return;
    }
    const space = this.ws.space();
    const sprintId = space === 'features' ? (this.ws.activeSprint()?.id ?? null) : null;
    this.issues
      .create({ type: 'task', title, space, status, sprintId, priority: 1, points: 0 })
      .subscribe(() => {
        this.cancelAdd();
        this.load(space, sprintId ?? undefined);
      });
  }

  drop(event: CdkDragDrop<Issue[]>, target: Status) {
    this.dragOver.set(null);
    if (event.previousContainer === event.container) {
      moveItemInArray(event.container.data, event.previousIndex, event.currentIndex);
      this.refresh();
      return;
    }
    const issue = event.previousContainer.data[event.previousIndex];
    const from = issue.status;
    transferArrayItem(
      event.previousContainer.data,
      event.container.data,
      event.previousIndex,
      event.currentIndex,
    );
    issue.status = target;
    if (issue.mondayItemId) issue.syncState = 'pending'; // will push to monday
    this.refresh();
    // Optimistic PATCH; revert on error. The backend write-through pushes the
    // new status to monday and returns the resulting sync state.
    this.issues.patch(issue.key, { status: target }).subscribe({
      next: (updated) => {
        issue.syncState = updated.syncState ?? issue.syncState;
        this.refresh();
      },
      error: () => {
        issue.status = from;
        if (issue.mondayItemId) issue.syncState = 'error';
        this.load(this.ws.space(), this.ws.activeSprint()?.id);
      },
    });
  }

  /** Rebuild the columns signal so counts/WIP recompute after a mutation. */
  private refresh() {
    this.columns.update((cols) => cols.map((c) => ({ ...c, count: c.issues.length })));
  }
}
