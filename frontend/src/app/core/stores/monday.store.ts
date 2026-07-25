import { Injectable, computed, inject, signal } from '@angular/core';

import { MondayService } from '../api/monday.service';
import { MondayBoard, MondayData } from '../models';
import { WorkspaceStore } from './workspace.store';

/** Global monday.com state — single source of truth for the top-bar Sync pill,
 *  the New Ticket board/group picker, and the monday page. Views watch `syncTick`
 *  to reload after a sync. */
@Injectable({ providedIn: 'root' })
export class MondayStore {
  private api = inject(MondayService);
  private ws = inject(WorkspaceStore);

  readonly connected = signal(false);
  readonly accountName = signal<string | null>(null);
  readonly boards = signal<MondayBoard[]>([]);
  readonly syncing = signal(false);
  readonly lastSyncedAt = signal<number | null>(null);
  readonly lastResult = signal<{ pulled: number; created: number; pushed: number } | null>(null);
  /** Bumped after every successful sync; views read it inside their load effect. */
  readonly syncTick = signal(0);
  private readonly now = signal(Date.now());

  readonly lastSyncedLabel = computed(() => {
    const t = this.lastSyncedAt();
    if (!t) return '';
    const s = Math.max(0, Math.round((this.now() - t) / 1000));
    if (s < 45) return 'just now';
    const m = Math.round(s / 60);
    return m < 60 ? `${m}m ago` : `${Math.round(m / 60)}h ago`;
  });

  constructor() {
    setInterval(() => this.now.set(Date.now()), 30000);
    this.refresh();
  }

  refresh() {
    this.api.get().subscribe((d: MondayData) => {
      this.connected.set(d.account.connected);
      this.accountName.set(d.account.accountName);
      this.boards.set(d.boards);
    });
  }

  sync() {
    if (this.syncing()) return;
    this.syncing.set(true);
    this.api.sync().subscribe({
      next: (r) => {
        this.syncing.set(false);
        this.lastSyncedAt.set(Date.now());
        this.lastResult.set({
          pulled: r.pulled ?? 0,
          created: r.imported ?? 0,
          pushed: r.pushed ?? 0,
        });
        this.syncTick.update((v) => v + 1);
        this.refresh();
        this.ws.refreshCategories();
      },
      error: () => this.syncing.set(false),
    });
  }

  connect() {
    this.api.connect().subscribe(() => {
      this.syncTick.update((v) => v + 1);
      this.refresh();
      this.ws.refreshCategories();
    });
  }

  disconnect() {
    this.api.disconnect().subscribe(() => this.refresh());
  }

  /** Deep link to a monday item, built from the board's url (no backend field). */
  itemUrl(boardId?: string | null, itemId?: string | null): string | null {
    if (!boardId || !itemId) return null;
    const b = this.boards().find((x) => x.boardId === boardId);
    return b?.url ? `${b.url}/pulses/${itemId}` : null;
  }
}
