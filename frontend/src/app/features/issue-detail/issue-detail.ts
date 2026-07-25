import { Location } from '@angular/common';
import {
  ChangeDetectionStrategy,
  Component,
  ElementRef,
  computed,
  effect,
  inject,
  input,
  signal,
  viewChild,
} from '@angular/core';
import { Router } from '@angular/router';

import { CatalogService } from '../../core/api/catalog.service';
import { GithubService } from '../../core/api/github.service';
import { IssuesService, PatchIssueBody } from '../../core/api/issues.service';
import { CiStatus, Comment, IssueDetail, PullRequest, RepoLinks, Status } from '../../core/models';
import { CI_META, PRIORITY_META, PR_STATE_META, REVIEW_META, STATUS_META } from '../../core/theme';
import { AiStore, IDLE_AI } from '../../core/stores/ai.store';
import { WorkspaceStore } from '../../core/stores/workspace.store';
import { MondayStore } from '../../core/stores/monday.store';
import { AvatarComponent } from '../../shared/avatar';
import { BlockedPillComponent } from '../../shared/blocked-pill';
import { ComboboxComponent } from '../../shared/combobox';
import { CiDotComponent } from '../../shared/ci-dot';
import { LabelChipComponent } from '../../shared/label-chip';
import { MondayBadgeComponent } from '../../shared/monday-badge';
import { MondayStatusComponent } from '../../shared/monday-status';
import { PriorityBarsComponent } from '../../shared/priority-bars';
import { ProgressBarComponent } from '../../shared/progress-bar';
import { StatusPillComponent } from '../../shared/status-pill';
import { ThinkingDotsComponent } from '../../shared/thinking-dots';
import { TypeBadgeComponent } from '../../shared/type-badge';

@Component({
  selector: 'app-issue-detail',
  standalone: true,
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [
    AvatarComponent,
    BlockedPillComponent,
    ComboboxComponent,
    CiDotComponent,
    LabelChipComponent,
    MondayBadgeComponent,
    MondayStatusComponent,
    PriorityBarsComponent,
    ProgressBarComponent,
    StatusPillComponent,
    ThinkingDotsComponent,
    TypeBadgeComponent,
  ],
  templateUrl: './issue-detail.html',
  styleUrl: './issue-detail.scss',
})
export class IssueDetailComponent {
  readonly key = input.required<string>();

  private issues = inject(IssuesService);
  private github = inject(GithubService);
  private router = inject(Router);
  private location = inject(Location);
  readonly ai = inject(AiStore);
  readonly ws = inject(WorkspaceStore);
  readonly monday = inject(MondayStore);
  private catalog = inject(CatalogService);

  readonly issue = signal<IssueDetail | null>(null);
  readonly loading = signal(true);
  readonly commentText = signal('');
  readonly aiThinking = signal(false);
  // Mentioning any of these in a comment asks the AI to research the code and reply.
  private readonly AI_MENTION = /(^|\s)@(ai|cadence|cadence-ai)\b/i;

  // --- @mention autocomplete ---
  readonly mentionOpen = signal(false);
  readonly mentionQuery = signal('');
  private mentionStart = -1;
  private composerTa = viewChild<ElementRef<HTMLTextAreaElement>>('composerTa');

  readonly mentionMatches = computed(() => {
    const q = this.mentionQuery();
    const ai = { initials: 'AI', name: 'risr/crm AI', color: '#003f75', isAi: true };
    const people = this.ws
      .members()
      .map((m) => ({ initials: m.initials, name: m.name, color: m.color, isAi: false }));
    return [ai, ...people]
      .filter((m) => !q || m.name.toLowerCase().includes(q) || m.initials.toLowerCase().includes(q))
      .slice(0, 6);
  });

  // GitHub integration
  readonly githubLinks = signal<RepoLinks | null>(null);
  readonly connectingGh = signal(false);
  readonly repoInput = signal('northwind/cadence');
  readonly ghRepo = computed(() => this.githubLinks()?.repo ?? null);
  readonly ghBranches = computed(() => this.githubLinks()?.branches ?? []);
  readonly ghPrs = computed(() => this.githubLinks()?.prs ?? []);

  readonly priorityMeta = PRIORITY_META;
  readonly statusMeta = STATUS_META;
  readonly prMeta = PR_STATE_META;
  readonly ciMeta = CI_META;
  readonly reviewMeta = REVIEW_META;

  readonly aiState = computed(() => this.ai.issueStateMap()[this.key()] ?? IDLE_AI);
  readonly isFeature = computed(() => this.issue()?.type === 'epic');
  readonly isSupport = computed(() => this.issue()?.space === 'support');

  // editing state
  readonly STATUSES: Status[] = ['backlog', 'todo', 'inprogress', 'review', 'done'];
  readonly PRIORITIES = [0, 1, 2, 3];
  readonly addingTask = signal(false);
  readonly taskTitle = signal('');
  readonly menuOpen = signal(false);

  constructor() {
    effect(() => {
      const k = this.key();
      this.monday.syncTick();
      this.load(k);
    });
  }

  private load(key: string) {
    this.loading.set(true);
    this.issues.get(key).subscribe((i) => {
      this.issue.set(i);
      this.loading.set(false);
    });
    this.loadLinks(key);
  }

  private loadLinks(key: string) {
    this.github.links(key).subscribe((l) => this.githubLinks.set(l));
  }

  onRepoInput(e: Event) {
    this.repoInput.set((e.target as HTMLInputElement).value);
  }
  connectGithub() {
    const full = this.repoInput().trim();
    if (!full) return;
    this.connectingGh.set(true);
    this.github.connect(full).subscribe({
      next: () => {
        this.connectingGh.set(false);
        this.loadLinks(this.key());
      },
      error: () => this.connectingGh.set(false),
    });
  }
  readonly syncingGh = signal(false);
  syncGithub() {
    this.syncingGh.set(true);
    this.github.sync().subscribe({
      next: (res) => {
        this.githubLinks.update((l) => (l ? { ...l, repo: res.repo } : l));
        this.loadLinks(this.key());
        this.syncingGh.set(false);
      },
      error: () => this.syncingGh.set(false),
    });
  }
  disconnectGithub() {
    this.github.disconnect().subscribe(() => this.loadLinks(this.key()));
  }

  back() {
    this.location.back();
  }
  go(key: string | undefined | null) {
    if (key) this.router.navigate(['/issues', key]);
  }

  createBranch() {
    this.issues.createBranch(this.key()).subscribe(() => this.load(this.key()));
  }

  // --- inline field editing (persisted) ---
  private patchAndReload(body: PatchIssueBody) {
    this.issues.patch(this.key(), body).subscribe(() => this.load(this.key()));
  }
  setStatus(e: Event) {
    this.patchAndReload({ status: (e.target as HTMLSelectElement).value as Status });
  }
  setAssignee(e: Event) {
    this.patchAndReload({ assigneeInitials: (e.target as HTMLSelectElement).value || null });
  }
  setPriority(e: Event) {
    this.patchAndReload({ priority: +(e.target as HTMLSelectElement).value });
  }
  setPoints(e: Event) {
    this.patchAndReload({ points: +(e.target as HTMLInputElement).value || 0 });
  }
  setSprint(e: Event) {
    this.patchAndReload({ sprintId: (e.target as HTMLSelectElement).value || null });
  }
  toggleBlocked() {
    this.patchAndReload({ blocked: !(this.issue()?.blocked ?? false) });
  }
  setOwner(e: Event) {
    this.patchAndReload({ ownerInitials: (e.target as HTMLSelectElement).value || null });
  }
  // Combobox emits the chosen value (existing or newly-typed). New values are
  // created in the catalog so they persist and show up everywhere.
  setProduct(value: string | null) {
    this.ensureCatalog('product', value);
    this.issues.patch(this.key(), { product: value }).subscribe(() => {
      this.load(this.key());
      this.ws.refreshCategories();
    });
  }
  setComponent(value: string | null) {
    this.ensureCatalog('component', value);
    this.issues.patch(this.key(), { component: value }).subscribe(() => {
      this.load(this.key());
      this.ws.refreshCategories();
    });
  }
  addRelease(value: string | null) {
    if (!value) return;
    this.ensureCatalog('release', value);
    const cur = this.issue()?.targetRelease ?? [];
    if (cur.includes(value)) return;
    this.patchAndReload({ targetRelease: [...cur, value] });
  }
  removeRelease(value: string) {
    const cur = (this.issue()?.targetRelease ?? []).filter((r) => r !== value);
    this.patchAndReload({ targetRelease: cur });
  }
  private ensureCatalog(kind: 'product' | 'component' | 'release', value: string | null) {
    if (value && !this.ws.catalog().some((c) => c.kind === kind && c.name === value)) {
      this.catalog.create(kind, value).subscribe(() => this.ws.refreshCatalog());
    }
  }
  setTaskId(e: Event) {
    this.patchAndReload({ taskId: (e.target as HTMLInputElement).value.trim() || null });
  }
  setTargetRelease(e: Event) {
    const parts = (e.target as HTMLInputElement).value
      .split(',')
      .map((s) => s.trim())
      .filter(Boolean);
    this.patchAndReload({ targetRelease: parts });
  }
  setTitle(e: Event) {
    const v = (e.target as HTMLInputElement).value.trim();
    if (v) this.patchAndReload({ title: v });
  }
  cap(s: string): string {
    return s.charAt(0).toUpperCase() + s.slice(1);
  }
  sprintName(id: string | null): string | null {
    if (!id) return null;
    return this.ws.sprints().find((s) => s.id === id)?.name ?? id;
  }

  // --- GitHub deep links (PR / branch open on github.com) ---
  prUrl(num: number): string {
    const full = this.ghRepo()?.fullName;
    return full ? `https://github.com/${full}/pull/${num}` : '';
  }
  branchUrl(name: string): string {
    const full = this.ghRepo()?.fullName;
    return full ? `https://github.com/${full}/tree/${name}` : '';
  }
  repoUrl(): string {
    const full = this.ghRepo()?.fullName;
    return full ? `https://github.com/${full}` : '';
  }

  // --- add child task (feature/epic) ---
  startAddTask() {
    this.addingTask.set(true);
    this.taskTitle.set('');
  }
  cancelAddTask() {
    this.addingTask.set(false);
    this.taskTitle.set('');
  }
  onTaskInput(e: Event) {
    this.taskTitle.set((e.target as HTMLInputElement).value);
  }
  submitTask() {
    const title = this.taskTitle().trim();
    const iss = this.issue();
    if (!title || !iss) {
      this.cancelAddTask();
      return;
    }
    this.issues
      .create({ type: 'task', title, space: iss.space, status: 'todo', featureKey: iss.key, priority: 1, points: 0 })
      .subscribe(() => {
        this.cancelAddTask();
        this.load(this.key());
      });
  }

  // --- delete ---
  toggleMenu() {
    this.menuOpen.update((v) => !v);
  }
  deleteIssue() {
    this.menuOpen.set(false);
    const linked = !!this.issue()?.mondayItemId;
    const msg = linked
      ? 'Delete this issue? This also deletes the linked item in monday.com. This cannot be undone.'
      : 'Delete this issue? This cannot be undone.';
    if (!confirm(msg)) return;
    this.issues.delete(this.key()).subscribe(() => {
      this.monday.refresh();
      this.back();
    });
  }

  summarize() {
    this.ai.summarize(this.key()).subscribe();
  }
  createPr() {
    this.ai.createPr(this.key()).subscribe((res) => this.issue.set(res.issue));
  }
  solve() {
    this.ai.solve(this.key()).subscribe((res) => this.issue.set(res.issue));
  }

  submitComment() {
    const body = this.commentText().trim();
    if (!body) return;
    this.issues.addComment(this.key(), body).subscribe((c) => {
      this.appendComment(c);
      this.commentText.set('');
      // Tagged the AI? It researches the code and replies as a comment.
      if (this.AI_MENTION.test(body)) this.askAi(body);
    });
  }

  private askAi(question: string) {
    this.aiThinking.set(true);
    this.ai.answer(this.key(), question).subscribe({
      next: (c) => {
        this.appendComment(c);
        this.aiThinking.set(false);
      },
      error: () => this.aiThinking.set(false),
    });
  }

  private appendComment(c: Comment) {
    this.issue.update((i) =>
      i ? { ...i, comments: [...i.comments, c], commentCount: i.commentCount + 1 } : i,
    );
  }

  onComment(e: Event) {
    const ta = e.target as HTMLTextAreaElement;
    const val = ta.value;
    this.commentText.set(val);
    // Show the @mention popup when the caret is inside an "@token" (no spaces).
    const caret = ta.selectionStart ?? val.length;
    const m = val.slice(0, caret).match(/@([\w-]*)$/);
    if (m) {
      this.mentionStart = caret - m[0].length;
      this.mentionQuery.set(m[1].toLowerCase());
      this.mentionOpen.set(true);
    } else {
      this.mentionOpen.set(false);
    }
  }

  insertMention(m: { name: string; isAi: boolean }) {
    const val = this.commentText();
    const end = this.mentionStart + 1 + this.mentionQuery().length;
    const token = m.isAi ? 'ai' : m.name; // @ai triggers the AI; people tag by name
    const next = `${val.slice(0, this.mentionStart)}@${token} ${val.slice(end)}`;
    this.commentText.set(next);
    this.mentionOpen.set(false);
    const pos = this.mentionStart + token.length + 2; // caret after "@token "
    setTimeout(() => {
      const el = this.composerTa()?.nativeElement;
      if (el) {
        el.focus();
        el.setSelectionRange(pos, pos);
      }
    });
  }

  /** Synthesize a 3-item CI checklist from the PR's overall status. */
  ciChecks(pr: PullRequest): { name: string; status: CiStatus }[] {
    const s = pr.checks;
    if (s === 'passing')
      return [
        { name: 'build', status: 'passing' },
        { name: 'unit tests', status: 'passing' },
        { name: 'lint', status: 'passing' },
      ];
    if (s === 'failing')
      return [
        { name: 'build', status: 'failing' },
        { name: 'unit tests', status: 'passing' },
        { name: 'lint', status: 'passing' },
      ];
    return [
      { name: 'build', status: 'pending' },
      { name: 'unit tests', status: 'pending' },
      { name: 'lint', status: 'passing' },
    ];
  }

  time(iso: string): string {
    const d = new Date(iso);
    return new Intl.DateTimeFormat('en-US', {
      month: 'short',
      day: 'numeric',
      hour: 'numeric',
      minute: '2-digit',
    }).format(d);
  }
}
