import { Injectable, inject, signal } from '@angular/core';

import { YbugService } from '../api/ybug.service';
import { YbugAccount } from '../models';

/** Ybug connection state for the Settings card. When connected, Ybug feedback
 *  becomes board tickets (webhook in real time, or Sync/poll on localhost). */
@Injectable({ providedIn: 'root' })
export class YbugStore {
  private api = inject(YbugService);

  readonly connected = signal(false);
  readonly projectName = signal<string | null>(null);
  readonly ticketCount = signal(0);

  constructor() {
    this.refresh();
  }

  private apply(a: YbugAccount) {
    this.connected.set(a.connected);
    this.projectName.set(a.projectName);
    this.ticketCount.set(a.ticketCount);
  }

  refresh() {
    this.api.get().subscribe((a) => this.apply(a));
  }
  connect() {
    this.api.connect().subscribe((a) => this.apply(a));
  }
  disconnect() {
    this.api.disconnect().subscribe((a) => this.apply(a));
  }
}
