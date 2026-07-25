import { ChangeDetectionStrategy, Component, computed, input } from '@angular/core';
import { Label } from '../core/models';
import { softFill } from '../core/theme';

@Component({
  selector: 'app-label-chip',
  standalone: true,
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `<span class="chip" [style.background]="fill()" [style.color]="label().color">{{
    label().name
  }}</span>`,
  styles: [
    `
      .chip {
        display: inline-flex;
        align-items: center;
        padding: 1px 7px;
        border-radius: 6px;
        font-size: 10.5px;
        font-weight: 600;
        white-space: nowrap;
      }
    `,
  ],
})
export class LabelChipComponent {
  label = input.required<Label>();
  fill = computed(() => softFill(this.label().color, 13));
}
