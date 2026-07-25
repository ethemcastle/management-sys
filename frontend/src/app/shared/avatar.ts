import { ChangeDetectionStrategy, Component, computed, input } from '@angular/core';
import { MemberRef } from '../core/models';

@Component({
  selector: 'app-avatar',
  standalone: true,
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    @if (member(); as m) {
      <span
        class="av"
        [style.background]="m.color"
        [style.width.px]="size()"
        [style.height.px]="size()"
        [style.borderRadius.px]="rounded()"
        [style.fontSize.px]="fontSize()"
        [title]="m.name"
        >{{ m.initials }}</span
      >
    } @else {
      <span
        class="av unassigned"
        [style.width.px]="size()"
        [style.height.px]="size()"
        [style.borderRadius.px]="rounded()"
        title="Unassigned"
      ></span>
    }
  `,
  styles: [
    `
      .av {
        display: grid;
        place-items: center;
        color: #fff;
        font-weight: 700;
        font-family: var(--font-mono);
        flex-shrink: 0;
        line-height: 1;
        user-select: none;
      }
      .unassigned {
        background: transparent;
        border: 1.5px dashed var(--border-2);
      }
    `,
  ],
})
export class AvatarComponent {
  member = input<MemberRef | null>(null);
  size = input(24);
  rounded = input(7);
  fontSize = computed(() => Math.min(11, Math.max(9.5, this.size() * 0.42)));
}
