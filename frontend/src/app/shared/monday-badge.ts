import { ChangeDetectionStrategy, Component, input } from '@angular/core';

/** Small monday.com sync indicator: the tri-colour monday dots, tinted by state.
 *  synced = normal, pending = amber ring, error = red ring. Icon-only + tooltip. */
@Component({
  selector: 'app-monday-badge',
  standalone: true,
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <span class="mb" [class]="state()" [title]="tip()">
      <svg width="14" height="14" viewBox="0 0 24 24" aria-hidden="true">
        <circle cx="6" cy="12" r="2.5" fill="#ff3d57" />
        <circle cx="12" cy="12" r="2.5" fill="#ffcb00" />
        <circle cx="18" cy="12" r="2.5" fill="#00c875" />
      </svg>
    </span>
  `,
  styles: [
    `
      .mb {
        display: inline-flex;
        align-items: center;
        justify-content: center;
        width: 20px;
        height: 20px;
        border-radius: 6px;
        border: 1px solid transparent;
      }
      .mb.pending {
        border-color: var(--warning);
        background: var(--warning-soft);
      }
      .mb.error {
        border-color: var(--danger);
        background: var(--danger-soft);
      }
      .mb.pending svg,
      .mb.error svg {
        opacity: 0.85;
      }
    `,
  ],
})
export class MondayBadgeComponent {
  readonly state = input<'synced' | 'pending' | 'error'>('synced');

  tip() {
    switch (this.state()) {
      case 'pending':
        return 'Waiting to sync to monday.com';
      case 'error':
        return 'monday.com sync failed — will retry on next Sync';
      default:
        return 'Synced with monday.com';
    }
  }
}
