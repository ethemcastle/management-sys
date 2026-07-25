import { Injectable, inject, signal } from '@angular/core';

import { RecapsService } from '../api/recaps.service';
import { MeetingNote } from '../models';

/** Meeting recaps (Gemini "Take notes for me"). Live source is the Inbox
 *  mailbox (IMAP); a mock recap ships so the view works offline. */
@Injectable({ providedIn: 'root' })
export class RecapsStore {
  private api = inject(RecapsService);

  readonly recaps = signal<MeetingNote[]>([]);
  readonly connected = signal(false);
  readonly source = signal<string>('');
  readonly loading = signal(false);
  readonly syncing = signal(false);

  constructor() {
    this.refresh();
  }

  refresh() {
    this.loading.set(true);
    this.api.list().subscribe({
      next: (d) => {
        this.recaps.set(d.recaps);
        this.connected.set(d.connected);
        this.source.set(d.source);
        this.loading.set(false);
      },
      error: () => this.loading.set(false),
    });
  }

  sync() {
    this.syncing.set(true);
    this.api.sync().subscribe({
      next: (d) => {
        this.recaps.set(d.recaps);
        this.syncing.set(false);
      },
      error: () => this.syncing.set(false),
    });
  }
}
