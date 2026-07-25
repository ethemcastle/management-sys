import { Injectable, signal } from '@angular/core';

export interface Toast {
  id: number;
  message: string;
  actionLabel?: string;
  action?: () => void;
  tone?: 'default' | 'error';
}

@Injectable({ providedIn: 'root' })
export class ToastStore {
  readonly toasts = signal<Toast[]>([]);
  private seq = 0;

  show(
    message: string,
    opts: { actionLabel?: string; action?: () => void; tone?: Toast['tone']; timeout?: number } = {},
  ) {
    const id = ++this.seq;
    this.toasts.update((t) => [...t, { id, message, ...opts }]);
    setTimeout(() => this.dismiss(id), opts.timeout ?? 6000);
  }

  dismiss(id: number) {
    this.toasts.update((t) => t.filter((x) => x.id !== id));
  }
}
