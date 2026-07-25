import { Injectable, signal } from '@angular/core';
import { Space, Status } from '../models';

export interface NewIssuePrefill {
  space?: Space;
  status?: Status;
  sprintId?: string | null;
  featureKey?: string | null;
}

/** Cross-view UI state: top-bar filters + the "New issue" modal. */
@Injectable({ providedIn: 'root' })
export class UiStore {
  readonly search = signal('');
  readonly onlyMine = signal(false);

  // New-issue modal
  readonly newIssueOpen = signal(false);
  readonly newIssuePrefill = signal<NewIssuePrefill | null>(null);

  openNewIssue(prefill?: NewIssuePrefill) {
    this.newIssuePrefill.set(prefill ?? null);
    this.newIssueOpen.set(true);
  }
  closeNewIssue() {
    this.newIssueOpen.set(false);
  }

  clear() {
    this.search.set('');
    this.onlyMine.set(false);
  }
}
