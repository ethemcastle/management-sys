import { ChangeDetectionStrategy, Component, computed, effect, inject, signal } from '@angular/core';
import { Router } from '@angular/router';

import { IssuesService } from '../../core/api/issues.service';
import { ViewsService } from '../../core/api/views.service';
import { Dashboard, Issue, PullRequest, SprintHealth, Status } from '../../core/models';
import { CI_META, PR_STATE_META, STATUS_META } from '../../core/theme';
import { AiStore } from '../../core/stores/ai.store';
import { MondayStore } from '../../core/stores/monday.store';
import { ToastStore } from '../../core/stores/toast.store';
import { WorkspaceStore } from '../../core/stores/workspace.store';
import { ActionRowComponent } from '../../shared/action-row';
import { AvatarComponent } from '../../shared/avatar';
import { BlockedPillComponent } from '../../shared/blocked-pill';
import { CiDotComponent } from '../../shared/ci-dot';
import { MondayStatusComponent } from '../../shared/monday-status';
import { PriorityBarsComponent } from '../../shared/priority-bars';
import { ProgressBarComponent } from '../../shared/progress-bar';
import { StatusPillComponent } from '../../shared/status-pill';
import { TypeBadgeComponent } from '../../shared/type-badge';

interface Seg {
  color: string;
  pct: number;
  label: string;
  value: number;
}

interface WorkGroup {
  label: string;
  items: Issue[];
}

@Component({
  selector: 'app-home',
  standalone: true,
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [
    ActionRowComponent,
    AvatarComponent,
    BlockedPillComponent,
    CiDotComponent,
    MondayStatusComponent,
    PriorityBarsComponent,
    ProgressBarComponent,
    StatusPillComponent,
    TypeBadgeComponent,
  ],
  templateUrl: './home.html',
  styleUrl: './home.scss',
})
export class HomeComponent {
  private views = inject(ViewsService);
  private issues = inject(IssuesService);
  private router = inject(Router);
  readonly ws = inject(WorkspaceStore);
  readonly ai = inject(AiStore);
  readonly monday = inject(MondayStore);
  private toast = inject(ToastStore);

  readonly data = signal<Dashboard | null>(null);
  readonly loading = signal(true);

  readonly prMeta = PR_STATE_META;
  readonly ciMeta = CI_META;

  readonly today = new Intl.DateTimeFormat('en-US', {
    weekday: 'long',
    month: 'long',
    day: 'numeric',
  }).format(new Date());

  readonly greeting = (() => {
    const h = new Date().getHours();
    return h < 12 ? 'Good morning' : h < 18 ? 'Good afternoon' : 'Good evening';
  })();

  readonly firstName = computed(() => this.ws.currentUser()?.name.split(' ')[0] ?? '');
  readonly dev = computed(() => this.data()?.developer ?? null);
  readonly po = computed(() => this.data()?.po ?? null);

  /** "Your work" grouped: Blocked first, then by status (in progress → backlog). */
  readonly workGroups = computed<WorkGroup[]>(() => {
    const items = this.dev()?.myFocus ?? [];
    const groups: WorkGroup[] = [];
    const blocked = items.filter((i) => i.blocked);
    if (blocked.length) groups.push({ label: 'Blocked', items: blocked });
    const order: Status[] = ['inprogress', 'review', 'todo', 'backlog'];
    for (const s of order) {
      const g = items.filter((i) => !i.blocked && i.status === s);
      if (g.length) groups.push({ label: STATUS_META[s].label, items: g });
    }
    return groups;
  });

  constructor() {
    effect(() => {
      const role = this.ws.role();
      const space = this.ws.space();
      this.monday.syncTick(); // re-pull the cockpit after any monday sync
      this.load(role, space);
    });
  }

  private load(role: 'developer' | 'product_owner', space: 'features' | 'support') {
    this.loading.set(true);
    this.views.dashboard(role, space).subscribe((d) => {
      this.data.set(d);
      this.loading.set(false);
    });
  }

  /** Segmented health bar: done / review / in-progress / to-do proportions. */
  healthSegments(h: SprintHealth): Seg[] {
    const total = h.done + h.review + h.inProgress + h.todo || 1;
    const defs: [number, string, string][] = [
      [h.done, STATUS_META.done.color, 'Done'],
      [h.review, STATUS_META.review.color, 'In review'],
      [h.inProgress, STATUS_META.inprogress.color, 'In progress'],
      [h.todo, STATUS_META.todo.color, 'To do'],
    ];
    return defs.map(([value, color, label]) => ({
      value,
      color,
      label,
      pct: (value / total) * 100,
    }));
  }

  go(key: string | undefined | null) {
    if (key) this.router.navigate(['/issues', key]);
  }

  prBranch(pr: PullRequest): string {
    return pr.branch ?? '';
  }

  copyStandup() {
    const text = (this.dev()?.standup ?? []).map((b) => `• ${b}`).join('\n');
    navigator.clipboard?.writeText(text).catch(() => {});
  }

  regenerate() {
    this.load(this.ws.role(), this.ws.space());
  }

  /** Unblock a ticket straight from the queue (optimistic-ish: reload + Undo). */
  resolveBlocked(key: string) {
    this.issues.patch(key, { blocked: false }).subscribe({
      next: () => {
        this.regenerate();
        this.toast.show(`Unblocked ${key}`, {
          actionLabel: 'Undo',
          action: () => this.issues.patch(key, { blocked: true }).subscribe(() => this.regenerate()),
        });
      },
      error: () => this.toast.show(`Couldn't unblock ${key}`, { tone: 'error' }),
    });
  }

  /** Sync monday from the cockpit; the syncTick effect reloads the queue. */
  syncMonday() {
    if (this.monday.syncing()) return;
    this.monday.sync();
    this.toast.show('Syncing monday…');
  }

  openReport() {
    this.ai.openPanel({ view: 'Reports', space: this.ws.space() });
    this.ai.ask('Draft the weekly report');
  }
}
