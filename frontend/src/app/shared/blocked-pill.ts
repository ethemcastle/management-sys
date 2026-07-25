import { ChangeDetectionStrategy, Component } from '@angular/core';

@Component({
  selector: 'app-blocked-pill',
  standalone: true,
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `<span class="bl">BLOCKED</span>`,
  styles: [
    `
      .bl {
        display: inline-flex;
        align-items: center;
        padding: 1px 6px;
        border-radius: 5px;
        font-size: 9.5px;
        font-weight: 700;
        letter-spacing: 0.04em;
        color: var(--danger);
        background: var(--danger-soft);
        border: 1px solid color-mix(in oklab, var(--danger) 30%, transparent);
        flex-shrink: 0;
      }
    `,
  ],
})
export class BlockedPillComponent {}
