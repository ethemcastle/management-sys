import { ChangeDetectionStrategy, Component, computed, input } from '@angular/core';

@Component({
  selector: 'app-progress-bar',
  standalone: true,
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <span class="track" [style.height.px]="height()">
      <span class="fill" [style.width.%]="pct()" [style.background]="color()"></span>
    </span>
  `,
  styles: [
    `
      .track {
        display: block;
        width: 100%;
        background: var(--surface-3);
        border-radius: 999px;
        overflow: hidden;
      }
      .fill {
        display: block;
        height: 100%;
        border-radius: 999px;
        transition: width 0.3s ease;
      }
    `,
  ],
})
export class ProgressBarComponent {
  value = input.required<number>();
  max = input(100);
  color = input('var(--accent)');
  height = input(6);
  pct = computed(() => {
    const m = this.max() || 1;
    return Math.max(0, Math.min(100, (this.value() / m) * 100));
  });
}
