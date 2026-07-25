import { Injectable, inject, signal } from '@angular/core';

import { ZoomService } from '../api/zoom.service';
import { ZoomAccount } from '../models';

/** Zoom connection state (for the Settings card). When connected, the Calendar
 *  recap is sourced from Zoom's AI Companion meeting summary. */
@Injectable({ providedIn: 'root' })
export class ZoomStore {
  private api = inject(ZoomService);

  readonly connected = signal(false);
  readonly accountName = signal<string | null>(null);

  constructor() {
    this.refresh();
  }

  private apply(a: ZoomAccount) {
    this.connected.set(a.connected);
    this.accountName.set(a.accountName);
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
