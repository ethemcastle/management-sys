import { Injectable, computed, inject, signal } from '@angular/core';
import { Observable, tap } from 'rxjs';

import { AiApiService, AssistantContext } from '../api/ai.service';
import {
  Comment,
  CreatePrResponse,
  PullRequest,
  SolveResponse,
  SuggestedResolution,
  SummarizeResponse,
} from '../models';

export type IssueAiPhase =
  | 'idle'
  | 'summarizing'
  | 'summarized'
  | 'creating'
  | 'solving'
  | 'done';

export interface IssueAiState {
  phase: IssueAiPhase;
  bullets: string[];
  resolution?: SuggestedResolution;
  createdPr?: PullRequest;
  changeSummary?: string;
  files: string[];
}

export const IDLE_AI: IssueAiState = { phase: 'idle', bullets: [], files: [] };
const IDLE = IDLE_AI;

type PanelPhase = 'idle' | 'busy' | 'done';

/** AI panel (global assistant) + per-issue AI card state machine. */
@Injectable({ providedIn: 'root' })
export class AiStore {
  private api = inject(AiApiService);

  // --- global slide-over panel ---
  readonly panelOpen = signal(false);
  readonly panelPhase = signal<PanelPhase>('idle');
  readonly panelBullets = signal<string[]>([]);
  readonly panelContext = signal<AssistantContext>({ view: 'Home', space: 'features' });

  openPanel(context?: Partial<AssistantContext>) {
    if (context) this.panelContext.update((c) => ({ ...c, ...context }));
    this.panelOpen.set(true);
  }
  closePanel() {
    this.panelOpen.set(false);
  }
  ask(question: string) {
    if (!question.trim()) return;
    this.panelPhase.set('busy');
    this.panelBullets.set([]);
    this.api.assistant(question, this.panelContext()).subscribe((res) => {
      this.panelBullets.set(res.bullets);
      this.panelPhase.set('done');
    });
  }
  resetPanel() {
    this.panelPhase.set('idle');
    this.panelBullets.set([]);
  }

  // --- per-issue AI card ---
  private issueStates = signal<Record<string, IssueAiState>>({});

  /** Reactive map of per-issue AI state (read `map()[key] ?? IDLE_AI`). */
  readonly issueStateMap = this.issueStates.asReadonly();

  issueState(key: string) {
    return computed<IssueAiState>(() => this.issueStates()[key] ?? IDLE);
  }

  private patch(key: string, next: Partial<IssueAiState>) {
    this.issueStates.update((m) => ({ ...m, [key]: { ...(m[key] ?? IDLE), ...next } }));
  }

  resetIssue(key: string) {
    this.issueStates.update((m) => ({ ...m, [key]: IDLE }));
  }

  summarize(key: string): Observable<SummarizeResponse> {
    this.patch(key, { phase: 'summarizing' });
    return this.api.summarize(key).pipe(
      tap((res) =>
        this.patch(key, {
          phase: 'summarized',
          bullets: res.bullets,
          resolution: res.suggestedResolution,
        }),
      ),
    );
  }

  createPr(key: string): Observable<CreatePrResponse> {
    this.patch(key, { phase: 'creating' });
    return this.api.createPr(key).pipe(
      tap((res) =>
        this.patch(key, {
          phase: 'done',
          createdPr: res.pr,
          changeSummary: `Opened PR #${res.pr.num} on ${res.pr.branch}`,
          files: this.issueStates()[key]?.resolution?.files ?? [],
        }),
      ),
    );
  }

  solve(key: string): Observable<SolveResponse> {
    this.patch(key, { phase: 'solving' });
    return this.api.solveTicket(key).pipe(
      tap((res) =>
        this.patch(key, {
          phase: 'done',
          createdPr: res.pr,
          changeSummary: res.summary,
          files: res.files,
        }),
      ),
    );
  }

  /** Ask the AI a question from a ticket comment; it researches the code and replies. */
  answer(key: string, question: string): Observable<Comment> {
    return this.api.answer(key, question);
  }
}
