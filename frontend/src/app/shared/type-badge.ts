import { ChangeDetectionStrategy, Component, computed, input } from '@angular/core';
import { IssueType } from '../core/models';
import { TYPE_META } from '../core/theme';

@Component({
  selector: 'app-type-badge',
  standalone: true,
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <span
      class="badge"
      [style.background]="meta().color"
      [style.width.px]="size()"
      [style.height.px]="size()"
      [style.fontSize.px]="fontSize()"
      [title]="type()"
      >{{ meta().letter }}</span
    >
  `,
  styles: [
    `
      .badge {
        display: grid;
        place-items: center;
        border-radius: 5px;
        color: #fff;
        font-weight: 700;
        font-family: var(--font-mono);
        flex-shrink: 0;
        line-height: 1;
      }
    `,
  ],
})
export class TypeBadgeComponent {
  type = input.required<IssueType>();
  size = input(17);
  meta = computed(() => TYPE_META[this.type()]);
  fontSize = computed(() => Math.round(this.size() * 0.6 * 10) / 10);
}
