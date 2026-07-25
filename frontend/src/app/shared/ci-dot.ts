import { ChangeDetectionStrategy, Component, computed, input } from '@angular/core';
import { CiStatus } from '../core/models';
import { CI_META } from '../core/theme';

@Component({
  selector: 'app-ci-dot',
  standalone: true,
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    @if (status() === 'pending') {
      <span class="ring spin" [style.--ci]="meta().color" [title]="'CI ' + meta().label"></span>
    } @else {
      <span class="dot" [style.background]="meta().color" [title]="'CI ' + meta().label"></span>
    }
  `,
  styles: [
    `
      .dot {
        display: inline-block;
        width: 8px;
        height: 8px;
        border-radius: 50%;
        flex-shrink: 0;
      }
      .ring {
        display: inline-block;
        width: 10px;
        height: 10px;
        border-radius: 50%;
        border: 1.6px solid var(--ci);
        border-top-color: transparent;
        flex-shrink: 0;
      }
    `,
  ],
})
export class CiDotComponent {
  status = input.required<CiStatus>();
  meta = computed(() => CI_META[this.status()]);
}
