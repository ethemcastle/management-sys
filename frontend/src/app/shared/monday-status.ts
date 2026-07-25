import { ChangeDetectionStrategy, Component, input } from '@angular/core';

/** The item's real monday status, shown verbatim with its monday colour (e.g.
 *  "Stuck" red, "Not Started" grey) — so Cadence keeps monday's statuses as-is
 *  instead of collapsing them into its own 5. */
@Component({
  selector: 'app-monday-status',
  standalone: true,
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <span class="mstat" [style.background]="tint()" [style.color]="color() || 'var(--text-2)'">
      <span class="dot" [style.background]="color() || '#c4c4c4'"></span>{{ label() }}
    </span>
  `,
  styles: [
    `
      .mstat {
        display: inline-flex;
        align-items: center;
        gap: 5px;
        font-size: 10.5px;
        font-weight: 700;
        padding: 2px 8px;
        border-radius: 6px;
        white-space: nowrap;
        max-width: 100%;
        overflow: hidden;
        text-overflow: ellipsis;
      }
      .dot {
        width: 6px;
        height: 6px;
        border-radius: 50%;
        flex: none;
      }
    `,
  ],
})
export class MondayStatusComponent {
  readonly label = input.required<string>();
  readonly color = input<string | null | undefined>(null);

  tint(): string {
    const c = this.color();
    return c ? c + '22' : 'var(--surface-2)';
  }
}
