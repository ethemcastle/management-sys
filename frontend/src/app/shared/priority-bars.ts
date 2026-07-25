import { ChangeDetectionStrategy, Component, computed, input } from '@angular/core';
import { priorityBars, priorityLabel } from '../core/theme';

@Component({
  selector: 'app-priority-bars',
  standalone: true,
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <span class="bars" [title]="label()">
      @for (c of bars(); track $index) {
        <span [style.background]="c" [style.height.px]="heights[$index]"></span>
      }
    </span>
  `,
  styles: [
    `
      .bars {
        display: inline-flex;
        align-items: flex-end;
        gap: 2px;
        flex-shrink: 0;
      }
      .bars > span {
        width: 3px;
        border-radius: 1px;
      }
    `,
  ],
})
export class PriorityBarsComponent {
  priority = input.required<number>();
  readonly heights = [6, 9, 12];
  bars = computed(() => priorityBars(this.priority()));
  label = computed(() => priorityLabel(this.priority()) + ' priority');
}
