import { ChangeDetectionStrategy, Component, inject } from '@angular/core';

import { ToastStore } from '../core/stores/toast.store';

@Component({
  selector: 'app-toast-host',
  standalone: true,
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <div class="toasts">
      @for (t of toast.toasts(); track t.id) {
        <div class="toast" [class.error]="t.tone === 'error'">
          <span class="msg">{{ t.message }}</span>
          @if (t.actionLabel) {
            <button class="act" (click)="run(t)">{{ t.actionLabel }}</button>
          }
          <button class="x" (click)="toast.dismiss(t.id)" aria-label="Dismiss">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor"
              stroke-width="2" stroke-linecap="round"><path d="M6 6l12 12M18 6L6 18" /></svg>
          </button>
        </div>
      }
    </div>
  `,
  styles: [
    `
      .toasts {
        position: fixed;
        right: 18px;
        bottom: 18px;
        z-index: 60;
        display: flex;
        flex-direction: column;
        gap: 9px;
      }
      .toast {
        display: flex;
        align-items: center;
        gap: 12px;
        background: var(--surface);
        border: 1px solid var(--border-2);
        border-radius: 10px;
        box-shadow: var(--shadow-pop);
        padding: 11px 12px 11px 14px;
        min-width: 260px;
        max-width: 380px;
        animation: cadSlideU 0.24s cubic-bezier(0.22, 1, 0.36, 1);
      }
      .toast.error {
        border-color: var(--danger);
      }
      .msg {
        font-size: 13px;
        color: var(--text);
        flex: 1;
      }
      .act {
        font-size: 12.5px;
        font-weight: 700;
        color: var(--accent);
        background: transparent;
        border: none;
        cursor: pointer;
        font-family: inherit;
        white-space: nowrap;
      }
      .x {
        border: none;
        background: transparent;
        color: var(--text-3);
        cursor: pointer;
        padding: 2px;
        display: inline-flex;
      }
      .x:hover {
        color: var(--text);
      }
      @keyframes cadSlideU {
        from {
          opacity: 0;
          transform: translateY(8px);
        }
        to {
          opacity: 1;
          transform: translateY(0);
        }
      }
    `,
  ],
})
export class ToastHostComponent {
  readonly toast = inject(ToastStore);

  run(t: { id: number; action?: () => void }) {
    t.action?.();
    this.toast.dismiss(t.id);
  }
}
