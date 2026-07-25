import {
  ChangeDetectionStrategy,
  Component,
  ElementRef,
  HostListener,
  computed,
  inject,
  signal,
  viewChild,
} from '@angular/core';
import { toSignal } from '@angular/core/rxjs-interop';
import { NavigationEnd, Router } from '@angular/router';
import { filter, map, startWith } from 'rxjs';

import { IssuesService } from '../core/api/issues.service';
import { Issue } from '../core/models';
import { AiStore } from '../core/stores/ai.store';
import { MondayStore } from '../core/stores/monday.store';
import { ToastStore } from '../core/stores/toast.store';
import { UiStore } from '../core/stores/ui.store';
import { WorkspaceStore } from '../core/stores/workspace.store';
import { AvatarComponent } from '../shared/avatar';
import { MondayStatusComponent } from '../shared/monday-status';
import { TypeBadgeComponent } from '../shared/type-badge';

const TITLES: Record<string, string> = {
  home: 'Home',
  board: 'Board',
  backlog: 'Backlog',
  timeline: 'Timeline',
  list: 'List',
  reports: 'Reports',
  issues: 'Issue',
  inbox: 'Inbox',
  calendar: 'Calendar',
  recaps: 'Recaps',
};

// Views that aren't scoped to a space (no "/ Features" breadcrumb suffix).
const SPACELESS = new Set(['Inbox', 'Calendar', 'Recaps']);

@Component({
  selector: 'app-top-bar',
  standalone: true,
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [TypeBadgeComponent, AvatarComponent, MondayStatusComponent],
  template: `
    <header class="topbar">
      <div class="crumb">
        <span class="view">{{ viewTitle() }}</span>
        @if (showSpace()) {
          <span class="sep">/</span>
          <span class="space">{{ ws.spaceInfo()?.name ?? '' }}</span>
        }
      </div>

      <div class="search-wrap">
        <label class="search">
          <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor"
            stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
            <circle cx="11" cy="11" r="7" /><path d="m20 20-3.2-3.2" /></svg>
          <input
            #searchInput
            type="text"
            placeholder="Search issues, keys, people…"
            [value]="ui.search()"
            (input)="onSearch($event)"
            (focus)="onFocus()"
            (blur)="onBlur()"
            (keydown.enter)="openTop()"
            (keydown.escape)="clearSearch()"
          />
          <span class="kbd">⌘K</span>
        </label>
        @if (showResults()) {
          <div class="sresults">
            @for (r of results(); track r.key) {
              <button class="sres" (mousedown)="openResult(r)">
                <app-type-badge [type]="r.type" [size]="16" />
                <span class="rk">{{ r.key }}</span>
                <span class="rt">{{ r.title }}</span>
                <span class="spacer"></span>
                @if (r.mondayStatus) {
                  <app-monday-status [label]="r.mondayStatus" [color]="r.mondayStatusColor ?? null" />
                }
                <app-avatar [member]="r.assignee" [size]="20" [rounded]="6" />
              </button>
            } @empty {
              <div class="snone">No matches for “{{ ui.search().trim() }}”</div>
            }
          </div>
        }
      </div>

      <div class="actions">
        @if (monday.connected()) {
          <button class="btn sync" (click)="sync()" [disabled]="monday.syncing()"
            title="Sync with monday.com">
            <span class="mdots" [class.spin]="monday.syncing()">
              <svg width="15" height="15" viewBox="0 0 24 24" aria-hidden="true">
                <circle cx="6" cy="12" r="2.5" fill="#ff3d57" /><circle cx="12" cy="12" r="2.5" fill="#ffcb00" />
                <circle cx="18" cy="12" r="2.5" fill="#00c875" /></svg>
            </span>
            {{ monday.syncing() ? 'Syncing…' : (monday.lastSyncedAt() ? 'Synced ' + monday.lastSyncedLabel() : 'Sync') }}
          </button>
        }
        @if (showFilter()) {
          <button class="btn ghost" [class.on]="ui.onlyMine()" (click)="toggleMine()">
            <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor"
              stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
              <path d="M3 5h18l-7 8v6l-4-2v-4z" /></svg>
            {{ ui.onlyMine() ? 'My issues' : 'Filter' }}
          </button>
        }
        <button class="btn ai" (click)="openAi()">
          <svg width="15" height="15" viewBox="0 0 24 24" fill="currentColor">
            <path d="M12 3l1.7 5.3L19 10l-5.3 1.7L12 17l-1.7-5.3L5 10l5.3-1.7z" /></svg>
          Ask AI
        </button>
        <button class="btn new" (click)="newIssue()">
          <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor"
            stroke-width="2.2" stroke-linecap="round"><path d="M12 5v14M5 12h14" /></svg>
          New
        </button>
      </div>
    </header>
  `,
  styles: [
    `
      .topbar {
        height: var(--topbar-h);
        flex-shrink: 0;
        border-bottom: 1px solid var(--border);
        background: var(--surface);
        display: flex;
        align-items: center;
        gap: 16px;
        padding: 0 18px;
      }
      .crumb {
        display: flex;
        align-items: center;
        gap: 8px;
        flex-shrink: 0;
      }
      .crumb .view {
        font-size: 14px;
        font-weight: 700;
        color: var(--text);
      }
      .crumb .sep {
        color: var(--text-3);
      }
      .crumb .space {
        font-size: 13px;
        color: var(--text-3);
        font-weight: 500;
      }
      .search-wrap {
        position: relative;
        flex: 1;
        max-width: 400px;
      }
      .sresults {
        position: absolute;
        top: calc(100% + 6px);
        left: 0;
        right: 0;
        background: var(--surface);
        border: 1px solid var(--border-2);
        border-radius: 10px;
        box-shadow: var(--shadow-pop);
        z-index: 45;
        padding: 5px;
        max-height: 60vh;
        overflow-y: auto;
      }
      .sres {
        display: flex;
        align-items: center;
        gap: 9px;
        width: 100%;
        text-align: left;
        padding: 8px 9px;
        border: none;
        background: transparent;
        border-radius: 7px;
        cursor: pointer;
        font-family: inherit;
      }
      .sres:hover {
        background: var(--surface-2);
      }
      .sres .spacer {
        flex: 1;
      }
      .rk {
        font-family: var(--font-mono);
        font-size: 11px;
        color: var(--text-3);
        flex: none;
      }
      .rt {
        font-size: 13px;
        color: var(--text);
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
        min-width: 0;
      }
      .snone {
        padding: 12px 10px;
        font-size: 12.5px;
        color: var(--text-3);
      }
      .search {
        display: flex;
        align-items: center;
        gap: 8px;
        width: 100%;
        background: var(--surface-2);
        border: 1px solid var(--border);
        border-radius: 9px;
        padding: 7px 11px;
        color: var(--text-3);
      }
      .search:focus-within {
        border-color: var(--border-2);
      }
      .search input {
        flex: 1;
        border: none;
        background: transparent;
        outline: none;
        color: var(--text);
        font-size: 13px;
        font-family: inherit;
      }
      .kbd {
        font-family: var(--font-mono);
        font-size: 10.5px;
        color: var(--text-3);
        border: 1px solid var(--border-2);
        border-radius: 5px;
        padding: 1px 5px;
      }
      .actions {
        display: flex;
        align-items: center;
        gap: 9px;
        margin-left: auto;
      }
      .btn {
        display: inline-flex;
        align-items: center;
        gap: 7px;
        padding: 7px 13px;
        border-radius: 8px;
        font-size: 13px;
        font-weight: 600;
        font-family: inherit;
        cursor: pointer;
        border: 1px solid var(--border);
        background: var(--surface);
        color: var(--text-2);
      }
      .btn:hover {
        border-color: var(--border-2);
        color: var(--text);
      }
      .btn.on {
        border-color: var(--accent-line);
        color: var(--accent);
        background: var(--accent-soft);
      }
      .btn.ai {
        border-color: var(--ai-line);
        color: var(--ai);
        background: transparent;
      }
      .btn.ai:hover {
        background: var(--ai-soft);
        color: var(--ai);
      }
      .btn.new {
        border: none;
        background: var(--accent);
        color: var(--accent-fg);
      }
      .btn.new:hover {
        filter: brightness(1.06);
        color: var(--accent-fg);
      }
      .btn.sync .mdots {
        display: inline-flex;
      }
      .btn.sync[disabled] {
        opacity: 0.7;
        cursor: default;
      }
      .mdots.spin {
        animation: cadSpin 0.9s linear infinite;
      }
    `,
  ],
})
export class TopBarComponent {
  readonly ws = inject(WorkspaceStore);
  readonly ui = inject(UiStore);
  readonly monday = inject(MondayStore);
  private toast = inject(ToastStore);
  private ai = inject(AiStore);
  private issuesApi = inject(IssuesService);
  private router = inject(Router);

  // --- global search ---
  private readonly searchInput = viewChild<ElementRef<HTMLInputElement>>('searchInput');
  private readonly allIssues = signal<Issue[]>([]);
  private readonly focused = signal(false);

  readonly results = computed<Issue[]>(() => {
    const q = this.ui.search().trim().toLowerCase();
    if (!q) return [];
    return this.allIssues()
      .map((i) => {
        const key = i.key.toLowerCase();
        const title = i.title.toLowerCase();
        const who = (i.assignee?.name ?? '').toLowerCase();
        let score = -1;
        if (key.includes(q)) score = 3;
        else if (title.startsWith(q)) score = 2;
        else if (title.includes(q)) score = 1;
        else if (who.includes(q)) score = 0;
        return { i, score };
      })
      .filter((x) => x.score >= 0)
      .sort((a, b) => b.score - a.score)
      .slice(0, 8)
      .map((x) => x.i);
  });
  readonly showResults = computed(() => this.focused() && this.ui.search().trim().length > 0);

  private url = toSignal(
    this.router.events.pipe(
      filter((e) => e instanceof NavigationEnd),
      map(() => this.router.url),
      startWith(this.router.url),
    ),
    { initialValue: this.router.url },
  );

  viewTitle = computed(() => {
    const seg = this.url().split('?')[0].split('/').filter(Boolean)[0] ?? 'home';
    return TITLES[seg] ?? 'Home';
  });

  showFilter = computed(() => ['Board', 'List', 'Backlog'].includes(this.viewTitle()));
  showSpace = computed(() => !SPACELESS.has(this.viewTitle()));

  onSearch(e: Event) {
    this.ui.search.set((e.target as HTMLInputElement).value);
  }
  onFocus() {
    this.focused.set(true);
    // Pull a fresh cross-space issue list to search over (cheap; whole workspace).
    this.issuesApi.list({ includeFeatures: true }).subscribe((all) => this.allIssues.set(all));
  }
  onBlur() {
    // Delay so a result mousedown registers before the dropdown closes.
    setTimeout(() => this.focused.set(false), 150);
  }
  openResult(i: Issue) {
    this.ui.search.set('');
    this.focused.set(false);
    this.router.navigate(['/issues', i.key]);
  }
  openTop() {
    const top = this.results()[0];
    if (top) this.openResult(top);
  }
  clearSearch() {
    this.ui.search.set('');
    this.focused.set(false);
    this.searchInput()?.nativeElement.blur();
  }

  /** ⌘K / Ctrl+K focuses the global search from anywhere. */
  @HostListener('document:keydown', ['$event'])
  onDocKey(e: KeyboardEvent) {
    if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'k') {
      e.preventDefault();
      this.searchInput()?.nativeElement.focus();
    }
  }

  toggleMine() {
    this.ui.onlyMine.update((v) => !v);
  }
  openAi() {
    this.ai.openPanel({ view: this.viewTitle(), space: this.ws.space() });
  }

  newIssue() {
    this.ui.openNewIssue({ space: this.ws.space() });
  }

  sync() {
    if (this.monday.syncing()) return;
    const before = this.monday.lastSyncedAt();
    this.monday.sync();
    // Report the outcome once the result lands (poll the store's lastResult).
    const check = setInterval(() => {
      if (this.monday.syncing()) return;
      clearInterval(check);
      if (this.monday.lastSyncedAt() === before) return; // errored
      const r = this.monday.lastResult();
      if (!r) return;
      const bits = [
        r.created ? `${r.created} new` : '',
        r.pulled ? `${r.pulled} updated` : '',
        r.pushed ? `${r.pushed} pushed` : '',
      ].filter(Boolean);
      this.toast.show(bits.length ? `Synced — ${bits.join(', ')}` : 'monday is up to date');
    }, 200);
  }
}
