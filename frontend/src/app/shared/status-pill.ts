import { ChangeDetectionStrategy, Component, computed, input } from '@angular/core';
import { Status } from '../core/models';
import { STATUS_META, softFill } from '../core/theme';

@Component({
  selector: 'app-status-pill',
  standalone: true,
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <span class="pill" [style.background]="fill()" [style.color]="meta().color">
      {{ meta().label }}
    </span>
  `,
  styles: [
    `
      .pill {
        display: inline-flex;
        align-items: center;
        padding: 2px 8px;
        border-radius: 6px;
        font-size: 11px;
        font-weight: 600;
        white-space: nowrap;
        flex-shrink: 0;
      }
    `,
  ],
})
export class StatusPillComponent {
  status = input.required<Status>();
  meta = computed(() => STATUS_META[this.status()]);
  fill = computed(() => softFill(this.meta().color, 12));
}
